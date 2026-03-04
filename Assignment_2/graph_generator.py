import json
import numpy as np
import matplotlib.pyplot as plt
import sys

def plot_part1_goodput(all_results):
    print("\n" + "="*50)
    print("GOODPUT SUMMARY STATISTICS (Megabits/sec)")
    print("="*50)
    
    plt.figure(figsize=(10, 6))
    
    for server, data in all_results.items():
        times = [d["time"] for d in data]
        mbps = [d["goodput_bps"] / 1_000_000 for d in data] 
        
        plt.plot(times, mbps, marker='o', label=server)
        
        mbps_array = np.array(mbps)
        print(f"Server: {server}")
        print(f"  Min:    {np.min(mbps_array):.2f} Mbps")
        print(f"  Median: {np.median(mbps_array):.2f} Mbps")
        print(f"  Avg:    {np.mean(mbps_array):.2f} Mbps")
        print(f"  95th P: {np.percentile(mbps_array, 95):.2f} Mbps")
        print("-" * 50)

    plt.title("Time Series of Goodput Evolution")
    plt.xlabel("Time (Seconds)")
    plt.ylabel("Goodput (Megabits/Second)")
    plt.grid(True)
    plt.legend()
    
    plt.savefig("part1_goodput.png")
    print("\n[+] Plot saved as 'part1_goodput.png' in your current directory.")
    plt.close()

def plot_part2_tcp_metrics(all_results):
    """Generates the time series and scatter plots for a single representative server."""
    if not all_results:
        return
        
    # Automatically select the first server as the representative destination
    server_ip = list(all_results.keys())[0]
    data = all_results[server_ip]
    
    print(f"\n[*] Generating Part 2 visualizations for representative server: {server_ip}")
    
    times = [d["time"] for d in data]
    goodput = [d["goodput_bps"] / 1_000_000 for d in data]
    cwnd = [d["snd_cwnd"] for d in data]
    rtt = [d["rtt_ms"] for d in data]
    retrans = [d["total_retrans"] for d in data]

    # --- 1. Time Series Subplots ---
    fig, axs = plt.subplots(4, 1, figsize=(10, 12), sharex=True)
    fig.suptitle(f"TCP Time Series for {server_ip}", fontsize=16)

    axs[0].plot(times, goodput, marker='o', color='b')
    axs[0].set_ylabel("Goodput (Mbps)")
    axs[0].grid(True)

    axs[1].plot(times, cwnd, marker='s', color='g')
    axs[1].set_ylabel("CWND (Packets)")
    axs[1].grid(True)

    axs[2].plot(times, rtt, marker='^', color='r')
    axs[2].set_ylabel("RTT (ms)")
    axs[2].grid(True)

    axs[3].plot(times, retrans, marker='x', color='k')
    axs[3].set_ylabel("Retransmissions")
    axs[3].set_xlabel("Time (Seconds)")
    axs[3].grid(True)

    plt.tight_layout()
    ts_filename = f"part2_timeseries_{server_ip.replace('.', '_')}.png"
    plt.savefig(ts_filename, format='png')
    plt.close()
    print(f"[+] Saved time series plot to {ts_filename}")

    # --- 2. Scatter Plots ---
    fig, axs = plt.subplots(3, 1, figsize=(6, 15))
    fig.suptitle(f"TCP Scatter Plots for {server_ip}", fontsize=16)

    axs[0].scatter(cwnd, goodput, color='g')
    axs[0].set_xlabel("CWND (Packets)")
    axs[0].set_ylabel("Goodput (Mbps)")
    axs[0].grid(True)

    axs[1].scatter(rtt, goodput, color='r')
    axs[1].set_xlabel("RTT (ms)")
    axs[1].set_ylabel("Goodput (Mbps)")
    axs[1].grid(True)

    axs[2].scatter(retrans, goodput, color='k')
    axs[2].set_xlabel("Retransmissions")
    axs[2].set_ylabel("Goodput (Mbps)")
    axs[2].grid(True)

    plt.tight_layout()
    sc_filename = f"part2_scatter_{server_ip.replace('.', '_')}.png"
    plt.savefig(sc_filename, format='png')
    plt.close()
    print(f"[+] Saved scatter plot to {sc_filename}")

def main():
    json_filename = "tcp_metrics.json"
    print(f"[*] Loading data from {json_filename}...")
    
    try:
        with open(json_filename, "r") as f:
            all_results = json.load(f)
    except FileNotFoundError:
        print(f"[-] Error: '{json_filename}' not found")
        sys.exit(1)
        
    plot_part1_goodput(all_results)
    plot_part2_tcp_metrics(all_results)

if __name__ == "__main__":
    main()