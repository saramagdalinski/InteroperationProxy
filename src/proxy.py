import socket

HOST = 'localhost'
PORT = 8000

SERVER_HOST = 'localhost'
SERVER_PORT = 9000

def handle_client(conn):
    request = conn.recv(1024).decode()
    print("HTTP request:\n", request)

    # Extract path
    try:
        first_line = request.split("\n")[0]
        path = first_line.split(" ")[1]  # /hello
        msg = path.lstrip("/")           # hello
    except:
        conn.close()
        return

    # Translate to custom protocol
    tcp_msg = f"GET {msg}"

    # Send to TCP server
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((SERVER_HOST, SERVER_PORT))
        s.sendall(tcp_msg.encode())
        response = s.recv(1024).decode()

    print("Response from server:", response)

    # Convert back to HTTP
    http_response = (
        "HTTP/1.1 200 OK\r\n"
        "Content-Type: text/plain\r\n"
        "\r\n"
        f"{response}"
    )

    conn.sendall(http_response.encode())
    conn.close()

def main():
    proxy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    proxy.bind((HOST, PORT))
    proxy.listen()

    print(f"Proxy listening on {PORT}...")

    while True:
        conn, addr = proxy.accept()
        handle_client(conn)

if __name__ == "__main__":
    main()