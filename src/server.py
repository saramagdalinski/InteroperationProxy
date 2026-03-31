import socket
import threading

CONTENT_STORE = {
    "/content/hello": "Hello World\n",
    "/content/test": "Test Content\n"
}

SOCKET_FILE = "/tmp/ndn-router.sock"

def handle_interest(conn, data):
    print(f"[Server] Received Interest: {data}")
    response = "ERROR INVALID_REQUEST"
    if data.startswith("INTEREST"):
        parts = data.split(" ", 1)
        if len(parts) > 1:
            name = parts[1]
            
            # Support returning data for nested namespace requests
            matched_data = None
            for prefix, payload in CONTENT_STORE.items():
                if name.startswith(prefix):
                    matched_data = payload
                    break
                    
            if matched_data:
                response = f"DATA {name} {matched_data}"
            else:
                response = f"DATA {name} NOT_FOUND"

    try:
        conn.sendall(response.encode())
    except Exception as e:
        print(f"[Server] Error sending data: {e}")

def main():
    # Connect to the NDN router
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        server.connect(SOCKET_FILE)
    except Exception as e:
        print(f"[Server] Error: NDN Router is not running at {SOCKET_FILE} ({e})")
        return

    # Register the prefix this server handles
    prefix = "/content"
    print(f"[Server] Connected to NDN Router. Registering prefix: {prefix}")
    server.sendall(f"REGISTER {prefix}".encode())

    print("[Server] Listening for interests from the network...")
    
    try:
        while True:
            data = server.recv(2048).decode()
            if not data:
                print("[Server] Connection to router closed.")
                break
            
            # Handle interest in a separate thread so server can keep reading from router
            thread = threading.Thread(target=handle_interest, args=(server, data))
            thread.daemon = True
            thread.start()
    except KeyboardInterrupt:
        print("\n[Server] Shutting down.")
    finally:
        server.close()

if __name__ == "__main__":
    main()