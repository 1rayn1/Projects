import asyncio
import json
import uuid

clients = {}  # client_id -> writer

async def handle_client(reader, writer):
    client_id = str(uuid.uuid4())
    clients[client_id] = writer
    addr = writer.get_extra_info("peername")
    print(f"[+] Client connected: {client_id} from {addr}")

    # Send welcome with assigned ID
    welcome = {"type": "welcome", "id": client_id}
    writer.write((json.dumps(welcome) + "\n").encode("utf-8"))
    await writer.drain()

    try:
        while True:
            data = await reader.readline()
            if not data:
                break

            try:
                msg = json.loads(data.decode("utf-8").strip())
            except json.JSONDecodeError:
                print(f"[!] Invalid JSON from {client_id}: {data!r}")
                continue

            target = msg.get("to")
            payload = msg.get("payload")

            if not target or payload is None:
                print(f"[!] Malformed message from {client_id}: {msg}")
                continue

            # Special target 'server' -> handle server commands
            if target == "server":
                # For now only support LIST
                if isinstance(payload, str) and payload.upper() == "LIST":
                    ids = list(clients.keys())
                    out = {"from": "server", "payload": "LIST:" + ",".join(ids)}
                    writer.write((json.dumps(out) + "\n").encode("utf-8"))
                    await writer.drain()
                else:
                    out = {"from": "server", "payload": "UNKNOWN_COMMAND"}
                    writer.write((json.dumps(out) + "\n").encode("utf-8"))
                    await writer.drain()
                continue

            if target not in clients:
                print(f"[!] Target {target} not connected (from {client_id})")
                # Inform sender
                out = {"from": "server", "payload": f"ERROR:Target {target} not connected"}
                writer.write((json.dumps(out) + "\n").encode("utf-8"))
                await writer.drain()
                continue

            out = {
                "from": client_id,
                "payload": payload
            }
            out_writer = clients[target]
            out_writer.write((json.dumps(out) + "\n").encode("utf-8"))
            await out_writer.drain()

    except Exception as e:
        print(f"[!] Error with client {client_id}: {e}")

    finally:
        print(f"[-] Client disconnected: {client_id}")
        try:
            del clients[client_id]
        except KeyError:
            pass
        writer.close()
        await writer.wait_closed()

async def main():
    host = "0.0.0.0"
    port = 9000
    server = await asyncio.start_server(handle_client, host, port)
    print(f"Relay server running on {host}:{port}")
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())