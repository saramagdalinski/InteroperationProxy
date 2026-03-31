import time
import urllib.request
import threading
import statistics
import matplotlib.pyplot as plt
import subprocess
import sys
import socket
import os

PROXY_URL = "http://localhost:8000/hello"
DIRECT_URL = "http://localhost:8080/hello"

CONCURRENCY_LEVELS = [1, 5, 10, 20, 50, 100]
NUM_REQUESTS_PER_THREAD = 10
NUM_RUNS = 5

ROUTER_SOCKET = "/tmp/ndn-router.sock"

# Direct Server for baseline comparsion
DIRECT_SERVER_CODE = """
from http.server import BaseHTTPRequestHandler, HTTPServer

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return  # Disable logging spam

    def do_GET(self):
        if self.path.startswith("/hello"):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Hello World\\n")
        elif self.path.startswith("/test"):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Test Content\\n")
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"NOT_FOUND")

server = HTTPServer(('localhost', 8080), Handler)
server.serve_forever()
"""

# Helper functions to wait for services to be ready
def wait_for_port(port, timeout=5.0):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection(('localhost', port), timeout=0.1):
                return True
        except:
            time.sleep(0.1)
    return False

def wait_for_socket(path, timeout=5.0):
    start = time.time()
    while time.time() - start < timeout:
        if os.path.exists(path):
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                    s.connect(path)
                return True
            except:
                pass
        time.sleep(0.1)
    return False

# Start the full system (router, server, proxy, direct server)
def start_system():
    print("Starting full system...\n")

    if os.path.exists(ROUTER_SOCKET):
        os.remove(ROUTER_SOCKET)

    router = subprocess.Popen([sys.executable, "router.py"])
    if not wait_for_socket(ROUTER_SOCKET):
        raise RuntimeError("Router failed to start")

    server = subprocess.Popen([sys.executable, "server.py"])
    time.sleep(1)

    proxy = subprocess.Popen([sys.executable, "proxy.py"])
    if not wait_for_port(8000):
        raise RuntimeError("Proxy failed to start")

    direct = subprocess.Popen([sys.executable, "-c", DIRECT_SERVER_CODE])
    if not wait_for_port(8080):
        raise RuntimeError("Direct HTTP server failed to start")

    print("System ready.\n")
    return router, server, proxy, direct

# Stop all processes and remove socket file
def stop_system(router, server, proxy, direct):
    print("\nShutting down system...")

    for proc in [proxy, server, router, direct]:
        proc.terminate()

    for proc in [proxy, server, router, direct]:
        proc.wait()

    if os.path.exists(ROUTER_SOCKET):
        os.remove(ROUTER_SOCKET)

# Functions to perform benchmark tests
def fetch(url, latencies, errors):
    for _ in range(NUM_REQUESTS_PER_THREAD):
        start = time.time()
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                response.read()
                latencies.append((time.time() - start) * 1000)
        except Exception as e:
            errors.append(str(e))

def run_test(url, concurrency):
    threads = []
    latencies = []
    errors = []

    start_time = time.time()

    for _ in range(concurrency):
        t = threading.Thread(target=fetch, args=(url, latencies, errors))
        threads.append(t)

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    total_time = time.time() - start_time

    total_requests = concurrency * NUM_REQUESTS_PER_THREAD
    success = len(latencies)
    error = len(errors)

    avg_latency = statistics.mean(latencies) if latencies else 0
    throughput = success / total_time if total_time > 0 else 0
    error_rate = (error / total_requests) * 100 if total_requests > 0 else 0

    return avg_latency, throughput, error_rate


def run_benchmark():
    proxy_latency = []
    direct_latency = []
    proxy_throughput = []
    proxy_errors = []

    for c in CONCURRENCY_LEVELS:
        print(f"Running concurrency {c}...")

        lat_runs = []
        thr_runs = []
        err_runs = []

        for _ in range(NUM_RUNS):
            p_lat, p_thr, p_err = run_test(PROXY_URL, c)
            lat_runs.append(p_lat)
            thr_runs.append(p_thr)
            err_runs.append(p_err)

            time.sleep(0.2)

        p_lat = statistics.mean(lat_runs)
        p_thr = statistics.mean(thr_runs)
        p_err = statistics.mean(err_runs)

        d_lat_runs = []
        for _ in range(NUM_RUNS):
            d_lat, _, _ = run_test(DIRECT_URL, c)
            d_lat_runs.append(d_lat)

        d_lat = statistics.mean(d_lat_runs)

        print(f"Proxy -> Lat: {p_lat:.2f} ms | Thr: {p_thr:.2f} req/s | Err: {p_err:.2f}%")
        print(f"Direct -> Lat: {d_lat:.2f} ms\n")

        proxy_latency.append(p_lat)
        direct_latency.append(d_lat)
        proxy_throughput.append(p_thr)
        proxy_errors.append(p_err)

    # Latency comparison plot
    plt.figure()
    plt.plot(CONCURRENCY_LEVELS, proxy_latency, marker='o', label='Proxy + NDN')
    plt.plot(CONCURRENCY_LEVELS, direct_latency, marker='s', label='Direct HTTP')
    plt.xlabel("Concurrency")
    plt.ylabel("Avg Latency (ms)")
    plt.title("Latency: Direct HTTP vs Proxy + NDN")
    plt.legend()
    plt.grid()
    plt.savefig("latency_comparison.png")

    # Throughput plot
    plt.figure()
    plt.plot(CONCURRENCY_LEVELS, proxy_throughput, marker='o')
    plt.xlabel("Concurrency")
    plt.ylabel("Requests/sec")
    plt.title("Throughput vs Concurrency (Proxy + NDN)")
    plt.grid()
    plt.savefig("throughput.png")

    # Error rate plot
    plt.figure()
    plt.plot(CONCURRENCY_LEVELS, proxy_errors, marker='o')
    plt.xlabel("Concurrency")
    plt.ylabel("Error Rate (%)")
    plt.title("Error Rate vs Concurrency (Proxy + NDN)")
    plt.grid()
    plt.savefig("error_rate.png")

    print("\nGenerated:")
    print("- latency_comparison.png")
    print("- throughput.png")
    print("- error_rate.png")

if __name__ == "__main__":
    router, server, proxy, direct = start_system()

    try:
        run_benchmark()
    finally:
        stop_system(router, server, proxy, direct)