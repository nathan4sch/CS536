#!/usr/bin/env python3
import argparse
import csv
import random
import re


IPV4_RE = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")


def is_ipv4(text: str) -> bool:
    if not IPV4_RE.match(text):
        return False
    parts = text.split(".")
    return all(0 <= int(p) <= 255 for p in parts)


def load_unique_ipv4_targets(csv_path: str) -> list[tuple[str, int]]:
    unique: dict[str, int] = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            host = (row.get("IP/HOST") or "").strip()
            port_str = (row.get("PORT") or "").strip()
            if not host or not port_str or not is_ipv4(host):
                continue

            try:
                port = int(port_str.split("-")[0])
            except ValueError:
                continue

            if host not in unique:
                unique[host] = port

    return list(unique.items())


def main() -> None:
    parser = argparse.ArgumentParser(description="Select random unique IPv4 servers from iperf CSV")
    parser.add_argument("--csv", required=True, help="Path to iperf3serverlist.csv")
    parser.add_argument("--count", required=True, type=int, help="Number of servers to select")
    args = parser.parse_args()

    if args.count < 1:
        raise SystemExit("count must be >= 1")

    items = load_unique_ipv4_targets(args.csv)
    if not items:
        return

    count = min(args.count, len(items))
    for ip, port in random.sample(items, count):
        print(f"{ip},{port}")


if __name__ == "__main__":
    main()
