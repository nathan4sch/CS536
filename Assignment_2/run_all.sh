#!/bin/bash
set -e

# defaults
N=10
T=15
F="tcp_metrics_train.json"

while getopts "n:t:f:" opt; do
  case $opt in
    n) N=$OPTARG ;;
    t) T=$OPTARG ;;
    f) F=$OPTARG ;;
  esac
done

echo "Running Experiments"
echo "$F"
python3 run_experiments.py -n "$N" -t "$T"
echo "Running ML"
python3 rwr.py -f "$F"
