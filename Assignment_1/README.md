# Assignment 1

## Requirements

- Python 3 with the executable name `python`
- `pip` (Python package manager)
- `ping` and `traceroute` utilities 

## Running the Code

Execute the run script:
```bash
bash run.sh
```

This will:
1. Create a Python virtual environment (if it doesn't exist)
2. Install matplotlib dependency
3. Run part1.py (queries IP geolocation and performs ping tests)
4. Run part2.py (performs traceroute analysis on selected hosts)

## Output Locations

- **Part 1 outputs:** `part1_outputs/`
  - `server_locations.csv` - Geolocation data for all servers
  - `rtt_vs_distance.pdf` - Scatter plot of distance vs RTT

- **Part 2 outputs:** `part2_outputs/`
  - `latency_breakdown.csv` - Detailed hop-by-hop latency breakdown
  - `latency_breakdown_stacked.pdf` - Stacked bar chart of incremental latency by hop
  - `hopcount_vs_rtt.pdf` - Scatter plot of hop count vs ping RTT
