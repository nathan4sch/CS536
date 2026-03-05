#!/usr/bin/env bash
set -euo pipefail

# Usage: ./run_cc_experiment.sh [cc_algo] [server_count_or_txt] [runs_per_server]
ALGO="${1:-dummycc}"
TARGET_SPEC="${2:-5}"
RUNS="${3:-2}"
DURATION=10
DEFAULT_PORT=5201

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CSV_PATH="$SCRIPT_DIR/../Assignment_2/iperf3serverlist.csv"
RESULTS_BASE_DIR="Results"
OUTPUT_ROOT="results_${ALGO}_batch_$(date +%Y%m%d_%H%M%S)"
LOADED_BY_SCRIPT=0

case "$ALGO" in
  dummycc|cubic|reno|all)
    ;;
  *)
    echo "Error: cc_algo must be one of: dummycc, cubic, reno, all"
    exit 1
    ;;
esac

if ! [[ "$RUNS" =~ ^[0-9]+$ ]] || [[ "$RUNS" -lt 1 ]]; then
  echo "Error: runs_per_server must be a positive integer"
  exit 1
fi

cleanup() {
  if [[ "$LOADED_BY_SCRIPT" -eq 1 ]]; then
    local unloaded=0
    for _ in {1..5}; do
      if sudo rmmod tcp_dummycc 2>/dev/null; then
        unloaded=1
        break
      fi
      sleep 1
    done

    if [[ "$unloaded" -eq 0 ]]; then
      echo "Warning: tcp_dummycc is still in use; unload it later with: sudo rmmod tcp_dummycc"
    fi
  fi
}
trap cleanup EXIT

unload_dummycc_with_retry() {
  local unloaded=0
  for _ in {1..20}; do
    if sudo rmmod tcp_dummycc 2>/dev/null; then
      unloaded=1
      break
    fi
    sleep 1
  done

  if [[ "$unloaded" -eq 1 ]]; then
    return 0
  fi

  return 1
}

cd "$SCRIPT_DIR"

if [[ "$ALGO" == "dummycc" || "$ALGO" == "all" ]]; then
  make
  if ! lsmod | awk '{print $1}' | grep -qx tcp_dummycc; then
    sudo insmod tcp_dummycc.ko
    LOADED_BY_SCRIPT=1
  fi
fi

ALLOWED="$(sysctl -n net.ipv4.tcp_allowed_congestion_control)"

if [[ "$ALGO" == "all" ]]; then
  for cc in dummycc cubic reno; do
    if [[ " $ALLOWED " != *" ${cc} "* ]]; then
      ALLOWED="${ALLOWED} ${cc}"
    fi
  done
  sudo sysctl -w "net.ipv4.tcp_allowed_congestion_control=${ALLOWED}" >/dev/null
else
  if [[ " $ALLOWED " != *" ${ALGO} "* ]]; then
    sudo sysctl -w "net.ipv4.tcp_allowed_congestion_control=${ALLOWED} ${ALGO}" >/dev/null
  fi
fi

TARGETS=()
if [[ "$TARGET_SPEC" =~ ^[0-9]+$ ]]; then
  if [[ "$TARGET_SPEC" -lt 1 ]]; then
    echo "Error: server_count must be a positive integer"
    exit 1
  fi
  if [[ ! -f "$CSV_PATH" ]]; then
    echo "Error: CSV file not found at $CSV_PATH"
    exit 1
  fi

  mapfile -t TARGETS < <(
    python3 "$SCRIPT_DIR/select_random_servers.py" \
      --csv "$CSV_PATH" \
      --count "$TARGET_SPEC"
  )

  if [[ "${#TARGETS[@]}" -lt "$TARGET_SPEC" ]]; then
    echo "Warning: requested $TARGET_SPEC servers, found only ${#TARGETS[@]} valid IPv4 targets"
  fi
else
  TARGET_FILE="$TARGET_SPEC"
  if [[ "$TARGET_FILE" != /* ]]; then
    TARGET_FILE="$SCRIPT_DIR/$TARGET_FILE"
  fi

  if [[ ! -f "$TARGET_FILE" ]]; then
    echo "Error: target file not found: $TARGET_FILE"
    exit 1
  fi

  while IFS= read -r raw_line || [[ -n "$raw_line" ]]; do
    line="${raw_line%%#*}"
    line="$(echo "$line" | xargs)"
    [[ -z "$line" ]] && continue

    server="$line"
    port="$DEFAULT_PORT"

    if [[ "$line" == *,* ]]; then
      server="${line%%,*}"
      port="${line##*,}"
    elif [[ "$line" == *:* ]]; then
      server="${line%%:*}"
      port="${line##*:}"
    fi

    server="$(echo "$server" | xargs)"
    port="$(echo "$port" | xargs)"

    if [[ -z "$server" ]]; then
      continue
    fi

    if ! [[ "$port" =~ ^[0-9]+$ ]]; then
      echo "Warning: invalid port '$port' for server '$server'; using $DEFAULT_PORT"
      port="$DEFAULT_PORT"
    fi

    TARGETS+=("$server,$port")
  done < "$TARGET_FILE"
fi

if [[ "${#TARGETS[@]}" -eq 0 ]]; then
  echo "Error: no targets to test"
  exit 1
fi

mkdir -p "$SCRIPT_DIR/$RESULTS_BASE_DIR/$OUTPUT_ROOT"

if [[ "$ALGO" == "all" ]]; then
  echo "Selected ${#TARGETS[@]} targets. Running $RUNS runs/target with dummycc, then unloading, then cubic+reno..."

  for target in "${TARGETS[@]}"; do
    IFS=',' read -r SERVER SERVER_PORT <<< "$target"
    SAFE_SERVER_NAME="${SERVER//./_}"
    SAFE_SERVER_NAME="${SAFE_SERVER_NAME//:/_}"
    SERVER_OUTPUT_DIR="$RESULTS_BASE_DIR/$OUTPUT_ROOT/$SAFE_SERVER_NAME"

    printf "\n=== Target (phase 1 dummycc): %s:%s ===\n" "$SERVER" "$SERVER_PORT"
    python3 "$SCRIPT_DIR/run_option1_tests.py" \
      --server "$SERVER" \
      --port "$SERVER_PORT" \
      --duration "$DURATION" \
      --runs "$RUNS" \
      --algos dummycc \
      --output-dir "$SERVER_OUTPUT_DIR"
  done

  if lsmod | awk '{print $1}' | grep -qx tcp_dummycc; then
    echo "Unloading tcp_dummycc before running cubic/reno (with retry)..."
    if ! unload_dummycc_with_retry; then
      echo "Error: failed to unload tcp_dummycc before cubic/reno runs."
      exit 1
    fi
    LOADED_BY_SCRIPT=0
  fi

  for target in "${TARGETS[@]}"; do
    IFS=',' read -r SERVER SERVER_PORT <<< "$target"
    SAFE_SERVER_NAME="${SERVER//./_}"
    SAFE_SERVER_NAME="${SAFE_SERVER_NAME//:/_}"
    SERVER_OUTPUT_DIR="$RESULTS_BASE_DIR/$OUTPUT_ROOT/$SAFE_SERVER_NAME"

    printf "\n=== Target (phase 2 cubic+reno): %s:%s ===\n" "$SERVER" "$SERVER_PORT"
    python3 "$SCRIPT_DIR/run_option1_tests.py" \
      --server "$SERVER" \
      --port "$SERVER_PORT" \
      --duration "$DURATION" \
      --runs "$RUNS" \
      --algos cubic reno \
      --output-dir "$SERVER_OUTPUT_DIR"
  done
else
  echo "Selected ${#TARGETS[@]} targets. Running $RUNS runs/target with ${ALGO}..."
  for target in "${TARGETS[@]}"; do
    IFS=',' read -r SERVER SERVER_PORT <<< "$target"
    SAFE_SERVER_NAME="${SERVER//./_}"
    SAFE_SERVER_NAME="${SAFE_SERVER_NAME//:/_}"
    SERVER_OUTPUT_DIR="$RESULTS_BASE_DIR/$OUTPUT_ROOT/$SAFE_SERVER_NAME"

    printf "\n=== Target: %s:%s ===\n" "$SERVER" "$SERVER_PORT"
    python3 "$SCRIPT_DIR/run_option1_tests.py" \
      --server "$SERVER" \
      --port "$SERVER_PORT" \
      --duration "$DURATION" \
      --runs "$RUNS" \
      --algos "$ALGO" \
      --output-dir "$SERVER_OUTPUT_DIR"
  done
fi

printf "\nBatch complete. Results saved in: %s/%s/%s\n" "$SCRIPT_DIR" "$RESULTS_BASE_DIR" "$OUTPUT_ROOT"
