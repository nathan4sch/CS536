import os
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

base_dir = Path(__file__).parent.parent.absolute()
results_dir = os.path.join(base_dir, "Results/results_all_batch_20260308_190129/23_249_60_154_SUCCESS")
plots_dir = os.path.join(base_dir, "Generate_Plots/Plots")

os.makedirs(plots_dir, exist_ok=True)

files = {
    "CUBIC": os.path.join(results_dir, "cubic_run1.csv"),
    "RENO": os.path.join(results_dir, "reno_run1.csv"),
    "Our CC": os.path.join(results_dir, "our_cc_run1.csv")
}

dfs = {}
for algo, path in files.items():
    if os.path.exists(path):
        dfs[algo] = pd.read_csv(path)
    else:
        print(f"Error: Could not find {path}")

def plot_metric(metric_col, ylabel, title, filename, is_step=False):
    plt.figure(figsize=(10, 6))
    
    for algo, df in dfs.items():
        t_start = df['timestamp_s'].min()
        t_normalized = df['timestamp_s'] - t_start
        
        if is_step:
            plt.step(t_normalized, df[metric_col], label=algo, where='post', alpha=0.8)
        else:
            plt.plot(t_normalized, df[metric_col], label=algo, marker='.', markersize=4, alpha=0.8)
    
    plt.xlabel("Time (seconds)")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.tight_layout()
    save_path = os.path.join(plots_dir, filename)
    plt.savefig(save_path, dpi=300)
    plt.close()
    print(f"Saved: {save_path}")

if dfs:
    plot_metric('goodput_mbps', 'Throughput (Mbps)', 'TCP Throughput Comparison', 'throughput_comparison.png')
    plot_metric('rtt_ms', 'RTT (ms)', 'Round Trip Time (RTT) Comparison', 'rtt_comparison.png')
    plot_metric('retransmits', 'Retransmissions', 'Loss / Retransmissions Over Time', 'loss_comparison.png', is_step=True)
    plot_metric('cwnd', 'Congestion Window Size', 'CWND Behavior Comparison', 'cwnd_comparison.png')
    
    print("\nAll plots successfully generated!")
else:
    print("No data loaded. Check your file paths.")