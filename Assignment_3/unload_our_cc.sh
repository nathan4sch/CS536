#!/usr/bin/env bash
set -euo pipefail

if lsmod | grep -q '^tcp_our_cc\b'; then
  sudo rmmod tcp_our_cc
fi
