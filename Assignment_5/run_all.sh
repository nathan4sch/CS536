#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

COMMAND="${1:-allgather}"

case "$COMMAND" in
  allgather)
    shift
    python3 "$SCRIPT_DIR/run_experiments.py" "$@"
    ;;
  broadcast)
    shift
    python3 "$SCRIPT_DIR/run_broadcast_experiments.py" "$@"
    ;;
  all)
    shift
    python3 "$SCRIPT_DIR/run_experiments.py" "$@"
    python3 "$SCRIPT_DIR/run_broadcast_experiments.py" "$@"
    ;;
  *)
    python3 "$SCRIPT_DIR/run_experiments.py" "$@"
    ;;
esac
