Instructions for running Part 2:
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

3. View the results in outputs/
