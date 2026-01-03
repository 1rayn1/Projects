import socket

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

def run_client(host="127.0.0.1", port=65432):
    print(f"Connecting to {host}:{port} ...")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((host, port))
        print("Connected. Waiting for game messages...")
        while True:
            try:
                line = recv_line(s)
            except ConnectionError as e:
                print(f"Disconnected: {e}")
                break

            if line.startswith("MSG:"):
                msg = line[len("MSG:"):].strip()
                print(msg)

            elif line.startswith("PROMPT:"):
                prompt = line[len("PROMPT:"):].strip()
                # Ask user for action
                resp = input(prompt)
                send_line(s, f"ACTION:{resp}")

            elif line.startswith("END:"):
                print("Game ended by server.")
                break

            else:
                # Unknown message type, just print raw
                print(line)

host = input("Enter server IP (default 127.0.0.1): ").strip() or "127.0.0.1"
port_str = input("Enter server port (default 65432): ").strip() or "65432"
port = int(port_str)
run_client(host, port)