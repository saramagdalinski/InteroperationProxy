import socket

HOST = 'localhost'
PORT = 9000

def handle_client(conn):
    data = conn.recv(1024).decode()
    print("Received from proxy:", data)

    if data.startswith("GET"):
        msg = data.split(" ", 1)[1]
        response = f"OK {msg}"
    else:
        response = "ERROR"

    conn.sendall(response.encode())
    conn.close()

def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen()

    print(f"Custom TCP Server listening on {PORT}...")

    while True:
        conn, addr = server.accept()
        handle_client(conn)

if __name__ == "__main__":
    main()