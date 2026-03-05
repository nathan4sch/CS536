#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
make
sudo insmod tcp_dummycc.ko || true
# Ensure it's selectable per-socket without editing sysctl globally
if ! sysctl net.ipv4.tcp_allowed_congestion_control | grep -q "dummycc"; then
  sudo sysctl -w "net.ipv4.tcp_allowed_congestion_control=$(sysctl -n net.ipv4.tcp_allowed_congestion_control) dummycc"
fi
sysctl net.ipv4.tcp_available_congestion_control
