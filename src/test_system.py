import sys
import unittest
import urllib.request
import urllib.error
import subprocess
import time
import socket
import os

ROUTER_SOCKET = "/tmp/ndn-router.sock"

class TestProxyServerSystem(unittest.TestCase):
    router_proc = None
    server_proc = None
    proxy_proc = None

    @classmethod
    def wait_for_port(cls, port, timeout=5.0):
        """Wait until a port is bound and listening."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                with socket.create_connection(('localhost', port), timeout=0.1):
                    return True
            except OSError:
                time.sleep(0.1)
        return False

    @classmethod
    def wait_for_socket(cls, path, timeout=5.0):
        """Wait until a unix socket is created and bound."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if os.path.exists(path):
                # Try to connect to ensure it's actually bound and listening
                try:
                    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                        s.connect(path)
                    return True
                except:
                    pass
            time.sleep(0.1)
        return False

    @classmethod
    def setUpClass(cls):
        # 1. Start NDN Router
        cls.router_proc = subprocess.Popen([sys.executable, 'router.py'])
        if not cls.wait_for_socket(ROUTER_SOCKET):
            cls.tearDownClass()
            raise RuntimeError(f"Router failed to create socket {ROUTER_SOCKET}")

        # 2. Start Server (registers with Router)
        cls.server_proc = subprocess.Popen([sys.executable, 'server.py'])
        time.sleep(1) # Give server a moment to register its prefix

        # 3. Start Proxy (HTTP gateway)
        cls.proxy_proc = subprocess.Popen([sys.executable, 'proxy.py'])
        if not cls.wait_for_port(8000):
            cls.tearDownClass()
            raise RuntimeError("HTTP Proxy failed to start on port 8000")

    @classmethod
    def tearDownClass(cls):
        # Clean up background processes
        if cls.proxy_proc: cls.proxy_proc.terminate()
        if cls.server_proc: cls.server_proc.terminate()
        if cls.router_proc: cls.router_proc.terminate()
        
        if cls.proxy_proc: cls.proxy_proc.wait()
        if cls.server_proc: cls.server_proc.wait()
        if cls.router_proc: cls.router_proc.wait()

    def test_hello_endpoint(self):
        url = "http://localhost:8000/hello"
        with urllib.request.urlopen(url) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.read().decode(), "Hello World\n")

    def test_test_endpoint(self):
        url = "http://localhost:8000/test"
        with urllib.request.urlopen(url) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.read().decode(), "Test Content\n")

    def test_not_found_endpoint(self):
        url = "http://localhost:8000/nonexistent"
        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(url)
        self.assertEqual(context.exception.code, 404)
        self.assertEqual(context.exception.read().decode(), "NOT_FOUND")

    def test_nested_prefix_endpoint(self):
        """Tests that the router and server properly handle hierarchical NDN paths like /content/hello/nested"""
        url = "http://localhost:8000/hello/nested/data"
        with urllib.request.urlopen(url) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.read().decode(), "Hello World\n")
            
    def test_z_server_down_resiliency(self):
        """Tests that if the downstream NDN server crashes, the Proxy survives and safely translates the route failure."""
        # Terminate the server process to simulate a hardware crash
        self.__class__.server_proc.terminate()
        self.__class__.server_proc.wait()
        
        # Give the router a fraction of a second to realize the IPC socket closed and purge its FIB
        time.sleep(0.5)
        
        url = "http://localhost:8000/hello"
        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(url)
            
        # Because the route is gone from the FIB, the router returns NACK NO_ROUTE natively,
        # which the proxy translates to an HTTP 502 Bad Gateway.
        self.assertEqual(context.exception.code, 502)
        self.assertEqual(context.exception.read().decode(), "Gateway Error: Upstream NDN Producer Offline or No Route Exists")



if __name__ == "__main__":
    unittest.main()
