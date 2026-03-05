# Assignment 3 - Option 1 (Kernel CC) Dummy Implementation

This directory contains a minimal TCP congestion-control kernel module (`dummycc`) and a Python runner that compares:
- `dummycc`
- `cubic`
- `reno`

using the existing iperf3-compatible socket workflow.

## Files
- `tcp_dummycc.c`: Linux TCP congestion-control module (dummy algorithm)
- `Makefile`: kernel module build file
- `load_dummycc.sh`: build + insert module
- `unload_dummycc.sh`: remove module
- `run_option1_tests.py`: socket test driver with `TCP_CONGESTION` selection and logging

## Dummy Algorithm Behavior
- Slow start until `cwnd >= ssthresh`
- Congestion avoidance: increase `cwnd` by 1 packet every 4 ACKed packets
- Loss reaction (`ssthresh`): reduce cwnd target to 75% (`3/4`) of current cwnd

## Build + Load
From this directory:

```bash
make
sudo insmod tcp_dummycc.ko
sysctl net.ipv4.tcp_available_congestion_control
```

Expected output should include `dummycc`.

## Run Throughput/RTT/Loss Comparison
Run 10-second tests with multiple runs per algorithm:

```bash
python3 run_option1_tests.py --server <IP_OR_HOST> --port 5201 --duration 10 --runs 3
```

This creates `results/` with:
- per-run CSVs: `<algo>_run<k>.csv` containing `timestamp_s, goodput_bps, rtt_ms, snd_cwnd, total_retrans`
- `summary.json` with run-level throughput summaries and failures

## Cleanup
```bash
sudo rmmod tcp_dummycc
make clean
```
