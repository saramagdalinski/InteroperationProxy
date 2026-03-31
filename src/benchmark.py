import time
import urllib.request
import threading
import statistics
import matplotlib.pyplot as plt

URL = "http://localhost:8000/hello"
CONCURRENCY_LEVELS = [1, 5, 10, 20, 50, 100]
NUM_REQUESTS_PER_THREAD = 10
NUM_RUNS = 10

def fetch(latencies, errors):
    for _ in range(NUM_REQUESTS_PER_THREAD):
        start = time.time()
        try:
            with urllib.request.urlopen(URL, timeout=5) as response:
                response.read()
                latencies.append((time.time() - start) * 1000) # Convert to ms
        except Exception as e:
            errors.append(str(e))

def run_benchmark():
    print(f"Averaging across {NUM_RUNS} runs per level...")
    print("Concurrency | Avg Latency (ms) | Avg Received | Avg Errors")
    print("-" * 65)
    
    # Store results for plotting
    plot_concurrency = []
    plot_latency = []
    plot_requests_sent = []
    plot_requests_received = []
    
    for c in CONCURRENCY_LEVELS:
        run_latencies = []
        total_errors = 0
        total_success = 0
        
        for _ in range(NUM_RUNS):
            threads = []
            latencies = []
            errors = []
            
            # We spawn `c` threads, each doing 10 requests consecutively
            for _ in range(c):
                t = threading.Thread(target=fetch, args=(latencies, errors))
                threads.append(t)
            
            for t in threads:
                t.start()
            for t in threads:
                t.join()
                
            run_latencies.extend(latencies)
            total_errors += len(errors)
            total_success += len(latencies)
        
        if run_latencies:
            avg_lat = statistics.mean(run_latencies)
        else:
            avg_lat = 0
            
        avg_received_per_run = total_success / NUM_RUNS
        avg_errors_per_run = total_errors / NUM_RUNS
            
        print(f"{c:^11} | {avg_lat:^16.2f} | {int(avg_received_per_run):^12} | {int(avg_errors_per_run):^10}")
        
        plot_concurrency.append(c)
        plot_latency.append(avg_lat)
        plot_requests_sent.append(c * NUM_REQUESTS_PER_THREAD)
        plot_requests_received.append(avg_received_per_run)
        
    try:
        # Plot 1: Latency Curve
        plt.figure(figsize=(8, 5))
        plt.plot(plot_concurrency, plot_latency, marker='o', linestyle='-', color='b')
        plt.title('Compound Session Latency vs. Concurrent Threads')
        plt.xlabel('Concurrent Threads (10 Requests Each)')
        plt.ylabel('Average Latency (ms)')
        plt.grid(True)
        output_file1 = "latency_graph.png"
        plt.savefig(output_file1)
        
        # Plot 2: Packets Sent vs Received (Throughput/Drop rate)
        plt.figure(figsize=(8, 5))
        plt.plot(plot_concurrency, plot_requests_sent, marker='s', linestyle='--', color='k', label='Packets Sent')
        plt.plot(plot_concurrency, plot_requests_received, marker='o', linestyle='-', color='g', label='Packets Received')
        plt.title('Network Reachability: Packets Sent vs. Received')
        plt.xlabel('Concurrent Threads')
        plt.ylabel('Total Packet Count')
        plt.legend()
        plt.grid(True)
        output_file2 = "packets_graph.png"
        plt.savefig(output_file2)
        
        print(f"\n[Success] Generated '{output_file1}' and '{output_file2}'!")
    except ImportError:
        print("\n[Notice] 'matplotlib' is not installed. Run 'pip install matplotlib' to automatically generate visual graphs.")

if __name__ == "__main__":
    print("Starting Interoperation Proxy Load Benchmark...\n")
    run_benchmark()
