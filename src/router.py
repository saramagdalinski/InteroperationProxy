import socket
import threading
import os

SOCKET_FILE = "/tmp/ndn-router.sock"

# Forwarding Information Base (FIB): Maps Name Prefix -> Server Socket Connection
FIB = {}
fib_lock = threading.Lock()

# Pending Interest Table (PIT): Maps Data Name -> List of Proxy Socket Connections waiting for it
PIT = {}
pit_lock = threading.Lock()

def handle_connection(conn):
    try:
        while True:
            # Wait for messages from any connected node (Proxy or Server)
            data = conn.recv(2048).decode()
            if not data:
                break
            
            print(f"[Router] Received: {data}")

            if data.startswith("REGISTER"):
                # Server is registering a prefix
                prefix = data.split(" ", 1)[1].strip()
                with fib_lock:
                    FIB[prefix] = conn
                print(f"[Router] Registered FIB entry: {prefix} -> {conn.getpeername() if hasattr(conn, 'getpeername') else 'Server'}")
                # We do not close the connection so the server can keep listening for interests

            elif data.startswith("INTEREST"):
                # Proxy is asking for data
                name = data.split(" ", 1)[1].strip()
                
                # 1. Add this connection to the PIT so we know who to send the data back to
                with pit_lock:
                    if name not in PIT:
                        PIT[name] = []
                    PIT[name].append(conn)
                
                # 2. Look up the name in the FIB
                target_conn = None
                longest_prefix_length = -1
                with fib_lock:
                    # Basic longest prefix match simulation
                    for prefix, server_conn in FIB.items():
                        if name.startswith(prefix) and len(prefix) > longest_prefix_length:
                            longest_prefix_length = len(prefix)
                            target_conn = server_conn
                
                # 3. Forward the interest, or return error if no route
                if target_conn:
                    try:
                        target_conn.sendall(data.encode())
                    except BrokenPipeError:
                        print(f"[Router] Server for {name} disconnected unexpectedly.")
                else:
                    print(f"[Router] No route found for {name}")
                    conn.sendall(f"NACK {name} NO_ROUTE".encode())
            
            elif data.startswith("DATA"):
                # Server sent data back
                parts = data.split(" ", 2)
                if len(parts) >= 2:
                    name = parts[1]
                    
                    # 1. Look up who wanted this data in the PIT
                    with pit_lock:
                        awaiting_conns = PIT.pop(name, [])
                    
                    # 2. Send the data to all proxies that requested it
                    for awaiting_conn in awaiting_conns:
                        try:
                            awaiting_conn.sendall(data.encode())
                        except Exception as e:
                            print(f"[Router] Failed to send to proxy: {e}")
                
    except Exception as e:
        print(f"[Router] Connection dropped: {e}")
    finally:
        # Clean up FIB if a server disconnected
        with fib_lock:
            for prefix in list(FIB.keys()):
                if FIB[prefix] == conn:
                    del FIB[prefix]
                    print(f"[Router] Removed disconnected server for prefix {prefix}")
        conn.close()

def main():
    if os.path.exists(SOCKET_FILE):
        os.remove(SOCKET_FILE)

    router = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    router.bind(SOCKET_FILE)
    router.listen()

    print(f"[Router] Central NDN Forwarding Daemon started at {SOCKET_FILE}")

    try:
        while True:
            conn, _ = router.accept()
            thread = threading.Thread(target=handle_connection, args=(conn,))
            thread.daemon = True
            thread.start()
    except KeyboardInterrupt:
        print("\n[Router] Shutting down.")
        router.close()
        if os.path.exists(SOCKET_FILE):
            os.remove(SOCKET_FILE)

if __name__ == "__main__":
    main()
