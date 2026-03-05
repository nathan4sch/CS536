#!/usr/bin/env bash
set -euo pipefail

if lsmod | grep -q '^tcp_dummycc\b'; then
  sudo rmmod tcp_dummycc
fi
