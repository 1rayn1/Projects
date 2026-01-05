import socket
import json

def send_line(conn, msg: str):
    if not msg.endswith("\n"):
        msg += "\n"
    conn.sendall(msg.encode("utf-8"))

def recv_line(conn) -> str:
    data = b""
    while True:
        chunk = conn.recv(1)
        if not chunk:
            raise ConnectionError("Connection closed by server.")
        if chunk == b"\n":
            break
        data += chunk
    return data.decode("utf-8").strip()

def relay_send(conn, to_id, payload: str):
    msg = {"to": to_id, "payload": payload}
    send_line(conn, json.dumps(msg))

def run_client(host="127.0.0.1", port=9000):
    print(f"Connecting to relay {host}:{port} ...")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((host, port))
        print("Connected to relay.")

        welcome_raw = recv_line(s)
        welcome = json.loads(welcome_raw)
        my_id = welcome["id"]
        print("Connected. Your relay ID (P2):", my_id)
        print("Share this ID with the host (P1).")

        other_id = input("Enter host's relay ID (P1): ").strip()

        print("Waiting for game messages...")
        while True:
            try:
                line = recv_line(s)
            except ConnectionError as e:
                print(f"Disconnected: {e}")
                break

            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                print("Invalid message from relay:", line)
                continue

            payload = msg.get("payload", "")

            if payload.startswith("MSG:"):
                msg_text = payload[len("MSG:"):].strip()
                print(msg_text)

            elif payload.startswith("PROMPT:"):
                prompt = payload[len("PROMPT:"):].strip()
                resp = input(prompt)
                relay_send(s, other_id, f"ACTION:{resp}")

            elif payload.startswith("END:"):
                print("Game ended by server.")
                break

            else:
                print(payload)

if __name__ == "__main__":
    host = input("Relay IP (default 127.0.0.1): ").strip() or "127.0.0.1"
    port_str = input("Relay port (default 9000): ").strip() or "9000"
    port = int(port_str)
    run_client(host, port)
