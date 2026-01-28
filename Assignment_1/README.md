Instructions for running Part 2 for environment:
1. Setup python environment
```console
python -m venv venv
source venv/bin/activate
pip install matplotlib
```

2. Run script
```console
python latency_breakdown.py --input listed_iperf3_servers.csv --count 5
```

3. View the output in outputs/

For write up:
Used codex for some of the code.

rtt does not have much of a correlation with hop count just based on the data. Maybe slightly positive.
