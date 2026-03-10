import os
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# Set up your specific absolute paths
base_dir = Path(__file__).parent.parent.absolute()
results_dir = os.path.join(base_dir, "Results/Graph_Results")
plots_dir = os.path.join(base_dir, "Generate_Plots/Average_Plots")

# Ensure the output directory exists
os.makedirs(plots_dir, exist_ok=True)

# Define the file mapping we are looking for in each subfolder
file_mapping = {
    "CUBIC": "cubic_run1.csv",
    "RENO": "reno_run1.csv",
    "Our CC": "our_cc_run1.csv"
}

# Dictionary to collect all DataFrames for each algorithm
all_data = {algo: [] for algo in file_mapping.keys()}

# 1. Iterate through all subfolders in the results directory
if os.path.exists(results_dir):
    for run_folder in os.listdir(results_dir):
        run_path = os.path.join(results_dir, run_folder)
        
        # Skip if it's not a directory
        if not os.path.isdir(run_path):
            continue
            
        # Extract the CSVs from this specific run
        for algo, filename in file_mapping.items():
            file_path = os.path.join(run_path, filename)
            if os.path.exists(file_path):
                df = pd.read_csv(file_path)
                
                # Normalize time so every run starts at t=0
                t_start = df['timestamp_s'].min()
                df['timestamp_s'] = df['timestamp_s'] - t_start
                
                # Round time to nearest 0.1s to align different runs for averaging
                df['time_bin'] = df['timestamp_s'].round(1)
                
                all_data[algo].append(df)
else:
    print(f"Error: Could not find results directory at {results_dir}")

# 2. Average the data across all runs
avg_dfs = {}
for algo, dfs_list in all_data.items():
    if dfs_list:
        # Combine all runs for this algorithm into one large DataFrame
        combined_df = pd.concat(dfs_list)
        
        # Group by the time_bin and calculate the mean for all metrics
        avg_df = combined_df.groupby('time_bin').mean().reset_index()
        avg_dfs[algo] = avg_df

# 3. Define the plotting function
def plot_average_metric(metric_col, ylabel, title, filename, is_step=False):
    plt.figure(figsize=(10, 6))
    
    for algo, df in avg_dfs.items():
        # Using time_bin as the X-axis since it's our aligned time
        if is_step:
            plt.step(df['time_bin'], df[metric_col], label=algo, where='post', alpha=0.8)
        else:
            plt.plot(df['time_bin'], df[metric_col], label=algo, marker='.', markersize=4, alpha=0.8)
    
    plt.xlabel("Time (seconds)")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.tight_layout()
    
    save_path = os.path.join(plots_dir, filename)
    plt.savefig(save_path, dpi=300)
    plt.close()
    print(f"Saved Average Plot: {save_path}")

# 4. Generate the plots if we successfully processed data
if avg_dfs:
    plot_average_metric('goodput_mbps', 'Average Throughput (Mbps)', 'TCP Throughput Comparison (Averaged)', 'avg_throughput_comparison.png')
    plot_average_metric('rtt_ms', 'Average RTT (ms)', 'Round Trip Time (RTT) Comparison (Averaged)', 'avg_rtt_comparison.png')
    plot_average_metric('retransmits', 'Average Retransmissions', 'Loss / Retransmissions Over Time (Averaged)', 'avg_loss_comparison.png', is_step=True)
    plot_average_metric('cwnd', 'Average Congestion Window Size', 'CWND Behavior Comparison (Averaged)', 'avg_cwnd_comparison.png')
    
    print("\nAll average plots successfully generated!")
else:
    print("No data loaded. Check your file paths and ensure the subfolders contain the expected CSV files.")