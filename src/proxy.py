import socket
import threading

HOST = 'localhost'
PORT = 8000
ROUTER_SOCKET = "/tmp/ndn-router.sock"

def handle_client(conn):
    try:
        request = conn.recv(1024).decode()
        if not request:
            return
            
        print("HTTP request:\n", request)

        # Extract HTTP path
        try:
            first_line = request.split("\n")[0]
            path = first_line.split(" ")[1]  # /hello
            msg = path.lstrip("/")           # hello
        except:
            return
            
        # Translate to NDN Interest
        content_name = f"/content/{msg}"
        ndn_interest_msg = f"INTEREST {content_name}"

        # Send to NDN network (no TCP/IP port routing, we just ask the network for a name)
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.connect(ROUTER_SOCKET)
                s.sendall(ndn_interest_msg.encode())
                
                # Wait for DATA from the NDN network
                response = s.recv(2048).decode()
        except Exception as e:
            print(f"[Proxy] NDN network is unreachable: {e}")
            conn.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
            return

        print("[Proxy] Response from NDN network:", response)

        # Translate NDN DATA back to HTTP
        if response.startswith("DATA"):
            parts = response.split(" ", 2)
            if len(parts) >= 3:
                name = parts[1]
                payload = parts[2]
            else:
                payload = ""

            if "NOT_FOUND" in payload:
                status_line = "HTTP/1.1 404 Not Found\r\n"
            else:
                status_line = "HTTP/1.1 200 OK\r\n"
        elif response.startswith("NACK"):
            status_line = "HTTP/1.1 502 Bad Gateway\r\n"
            payload = "Gateway Error: Upstream NDN Producer Offline or No Route Exists"
        else:
            status_line = "HTTP/1.1 500 Internal Server Error\r\n"
            payload = "Error processing NDN request"

        http_response = (
            status_line +
            "Content-Type: text/plain\r\n"
            "\r\n"
            f"{payload}"
        )

        conn.sendall(http_response.encode())
    except Exception as e:
        print(f"Error handling proxy client: {e}")
    finally:
        conn.close()

def main():
    proxy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    proxy.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    proxy.bind((HOST, PORT))
    proxy.listen()

    print(f"Interoperation Proxy listening for HTTP on port {PORT}...")

    try:
        while True:
            conn, addr = proxy.accept()
            thread = threading.Thread(target=handle_client, args=(conn,))
            thread.daemon = True
            thread.start()
    except KeyboardInterrupt:
        print("\nShutting down proxy.")
    finally:
        proxy.close()

if __name__ == "__main__":
    main()