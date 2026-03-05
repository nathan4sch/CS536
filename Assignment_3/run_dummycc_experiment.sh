#!/usr/bin/env bash
set -euo pipefail

# Usage: ./run_dummycc_experiment.sh [num_servers] [runs_per_server]
NUM_SERVERS="${1:-5}"
RUNS="${2:-2}"
DURATION=10

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CSV_PATH="$SCRIPT_DIR/../Assignment_2/iperf3serverlist.csv"
OUTPUT_ROOT="results_dummycc_batch_$(date +%Y%m%d_%H%M%S)"
RESULTS_BASE_DIR="Results"
LOADED_BY_SCRIPT=0

if ! [[ "$NUM_SERVERS" =~ ^[0-9]+$ ]] || [[ "$NUM_SERVERS" -lt 1 ]]; then
  echo "Error: num_servers must be a positive integer"
  exit 1
fi

if ! [[ "$RUNS" =~ ^[0-9]+$ ]] || [[ "$RUNS" -lt 1 ]]; then
  echo "Error: runs_per_server must be a positive integer"
  exit 1
fi

if [[ ! -f "$CSV_PATH" ]]; then
  echo "Error: CSV file not found at $CSV_PATH"
  exit 1
fi

cleanup() {
  if [[ "$LOADED_BY_SCRIPT" -eq 1 ]]; then
    sudo rmmod tcp_dummycc || true
  fi
}
trap cleanup EXIT

cd "$SCRIPT_DIR"

make

if ! lsmod | awk '{print $1}' | grep -qx tcp_dummycc; then
  sudo insmod tcp_dummycc.ko
  LOADED_BY_SCRIPT=1
fi

ALLOWED="$(sysctl -n net.ipv4.tcp_allowed_congestion_control)"
if [[ " $ALLOWED " != *" dummycc "* ]]; then
  sudo sysctl -w "net.ipv4.tcp_allowed_congestion_control=${ALLOWED} dummycc" >/dev/null
fi

mapfile -t TARGETS < <(
  python3 "$SCRIPT_DIR/select_random_servers.py" \
    --csv "$CSV_PATH" \
    --count "$NUM_SERVERS"
)

if [[ "${#TARGETS[@]}" -eq 0 ]]; then
  echo "Error: no valid IPv4 targets found in CSV"
  exit 1
fi

if [[ "${#TARGETS[@]}" -lt "$NUM_SERVERS" ]]; then
  echo "Warning: requested $NUM_SERVERS servers, found only ${#TARGETS[@]} valid IPv4 targets"
fi

mkdir -p "$SCRIPT_DIR/$RESULTS_BASE_DIR/$OUTPUT_ROOT"

echo "Selected ${#TARGETS[@]} servers. Running $RUNS runs/server with dummycc..."

for target in "${TARGETS[@]}"; do
  IFS=',' read -r SERVER_IP SERVER_PORT <<< "$target"
  SERVER_OUTPUT_DIR="$RESULTS_BASE_DIR/$OUTPUT_ROOT/${SERVER_IP//./_}"

  printf "\n=== Server: %s:%s ===\n" "$SERVER_IP" "$SERVER_PORT"
  python3 "$SCRIPT_DIR/run_option1_tests.py" \
    --server "$SERVER_IP" \
    --port "$SERVER_PORT" \
    --duration "$DURATION" \
    --runs "$RUNS" \
    --algos dummycc \
    --output-dir "$SERVER_OUTPUT_DIR"
done

printf "\nBatch complete. Results saved in: %s/%s/%s\n" "$SCRIPT_DIR" "$RESULTS_BASE_DIR" "$OUTPUT_ROOT"
