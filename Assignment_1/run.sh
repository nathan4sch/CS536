#!/bin/bash

if [ ! -d venv ]; then
    echo "Creating virtual environment..."
    python -m venv venv
fi

source venv/bin/activate

echo "Installing dependencies..."
pip install -q matplotlib

echo "Running part1.py..."
python part1.py

echo ""
echo "Running part2.py..."
python part2.py --input listed_iperf3_servers.csv --count 5

echo ""
echo "Done! Check part1_outputs/ and part2_outputs/ for results."
