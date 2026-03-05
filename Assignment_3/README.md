# MY README

## TODO
- Implement the actual congestion control algorithm
- Actually generate the right performance results. I don't know if the stuff generated in Reports/ now is actually what we want
    - Specifically what does it mean by loss values??
- Verify that our code does what it claims to do
- Write code to generate some plots of this stuff. We need to compare throughput values in one at least.

## How to run

The main script to run is `run_cc_experiment.sh`.
- The 1st argument is the cc algorithm to use. The options are ["dummycc", "cubic", "reno", "all"].
- The 2nd argument is the number of random servers to run on OR a text file containing a list of servers to run on
- The 3rd argument is the number of runs per server.
- This script sets up everything including the necessary environment stuff on my Ubuntu 24 laptop.

The script mostly does unreadable bash scripting stuff.

## How it knows what congestion control algorithm to use

When the code is ran with dummycc (a basic AI generated congested control algorithm, this is a placeholder for the one we make in part 2), we use `sudo insmod tcp_dummycc.ko` to register it into the kernal. This `.ko` file is generated from the related C file where the actual algorithm is written in C. 
For cubic/reno, the `net.ipv4.tcp_allowed_congestion_control` variable is updated to specify that algorithm.

In the actual code, in `iperf3_client.py` from `Assignment_2` `_make_tcp_socket()` is used with the algorithm as an option, which is passed inf rom the script calling it. cubic/reno use built-in kernel stuff so we do not have to do anything except specify with the string name in the function call.

When we are done using dummycc, `sudo rrmod tcp_dummycc` is used to unload it from the kernel.

## Using the socket program from Assignment 2

The script `run_option1_tests.py` calls `iperf3_client.py` from Assignment 2 and uses it as the socket. I had to change part of the file to make this work so hopefully that didn't break anything.




# END MY README
# ---------------------------------

# AI README BELOW
# PROBABLY USELESS
# Assignment 3 - Option 1 (Kernel CC) Implementation

This directory implements Option 1 using a Linux kernel module (`dummycc`) and a unified experiment runner that uses the Assignment 2 socket client directly.

## What Changed
- Replaced separate run scripts with one unified script: `run_cc_experiment.sh`.
- Added `all` mode to run `dummycc`, `cubic`, and `reno`.
- Added strict isolation behavior in `all` mode:
  - run `dummycc` first,
  - unload `tcp_dummycc`,
  - then run `cubic` + `reno`.
- Added retry logic when unloading `tcp_dummycc` to avoid transient "module in use" failures.
- Refactored random server selection into `select_random_servers.py` (no embedded Python in bash script).
- Added per-server algorithm comparison output: `algo_comparison.csv`.
- Updated Assignment 2 client integration:
  - Assignment 3 now imports and uses `Assignment_2/iperf3_client.py` directly.
  - Assignment 2 client now supports per-socket `TCP_CONGESTION` selection.
- Added cleanup and ignore support:
  - `cleanup_assignment3.sh`
  - `.gitignore` for build artifacts/results/cache files.

## Files
- `tcp_dummycc.c`: custom TCP congestion-control kernel module
- `Makefile`: kernel module build
- `run_cc_experiment.sh`: unified runner for `dummycc|cubic|reno|all`
- `run_option1_tests.py`: per-target test runner + CSV/JSON/comparison generation
- `select_random_servers.py`: selects random unique IPv4 targets from CSV
- `5servers.txt`: sample target list with 5 servers
- `cleanup_assignment3.sh`: removes generated/build files
- `.gitignore`: ignores Python/build/results artifacts

## Dummy Algorithm (dummycc)
- Slow start until `cwnd >= ssthresh`
- Congestion avoidance: increase cwnd by 1 packet every 4 ACKed packets
- Loss response (`ssthresh`): 75% of current cwnd

## How To Run
From `Assignment_3/`:

```bash
./run_cc_experiment.sh [cc_algo] [server_count_or_txt] [runs_per_server]
```

Defaults:
- `cc_algo`: `dummycc`
- `server_count_or_txt`: `5`
- `runs_per_server`: `2`

Valid `cc_algo` values:
- `dummycc`
- `cubic`
- `reno`
- `all`

Examples:
```bash
# Default (dummycc, 5 random servers, 2 runs each)
./run_cc_experiment.sh

# Run all three algorithms on servers listed in file
./run_cc_experiment.sh all 5servers.txt 2

# Run reno on 8 random servers, 3 runs each
./run_cc_experiment.sh reno 8 3
```

## Target Input Modes
Second argument supports either:
1. Integer count of random servers from `Assignment_2/iperf3serverlist.csv`
2. Path to a text file containing servers (`host`, `host:port`, or `host,port`)

## Output Structure
Outputs are written under:

`Assignment_3/Results/results_<algo>_batch_<timestamp>/`

Per target directory contains:
- `<algo>_run<k>.csv` (per-run samples)
- `summary.json` (run summaries)
- `algo_comparison.csv` (algorithm-level comparison for that target)

## Metrics Logged
Per-sample CSV columns:
- `timestamp_s`
- `goodput_bps`
- `throughput_mbps`
- `rtt_ms`
- `snd_cwnd`
- `total_retrans`
- `retrans_delta`
- `loss_events_per_s`

`summary.json` includes:
- `mean_mbps`, `median_mbps`, `min_mbps`, `max_mbps`
- `avg_rtt_ms`
- `total_loss_events`

`algo_comparison.csv` includes per algorithm:
- successful/failed run counts
- averaged throughput and RTT
- total loss events

## What We Learned
- Per-socket `TCP_CONGESTION` selection is the cleanest way to compare algorithms with the same client flow.
- Keeping `dummycc` loaded while testing `cubic/reno` works functionally, but explicit unload between phases in `all` mode gives cleaner isolation.
- Immediate module unload can fail transiently (`in use`) right after tests; retry-based unload is more reliable.
- Separating orchestration (bash), target selection (Python), and test execution (Assignment 2 client + Assignment 3 runner) keeps the workflow easier to debug and extend.

## Cleanup
```bash
./cleanup_assignment3.sh
```

Manual module unload if needed:
```bash
sudo rmmod tcp_dummycc
```
