import os

os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

import argparse
import csv
import random
import subprocess
from pathlib import Path

import matplotlib.pyplot as plt


def read_hosts(csv_path: Path) -> list[str]:
    with csv_path.open(newline="") as f:
        reader = csv.DictReader(f)
        hosts = []
        for row in reader:
            host = (row.get("IP/HOST") or "").strip()
            if host:
                hosts.append(host)
    return hosts


def run_traceroute(host: str, timeout_s: int) -> list[tuple[int, float]]:
    cmd = ["traceroute", "-n", "-q", "1", "-w", str(timeout_s), host]
    try:
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise SystemExit("traceroute not found. Please install traceroute.") from exc

    hop_rtts = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("traceroute"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        # print(f"{parts=}")
        hop_idx = int(parts[0])
        if "*" in parts:
            rtt = 0.0
        else:
            rtt = float(parts[2])
        hop_rtts.append((hop_idx, rtt))

    # Remove extra hops at end that are all unreachable
    i = 0
    for hop in reversed(hop_rtts):
        if hop[1] != 0.0:
            if i == 0:
                break
            hop_rtts = hop_rtts[0:-i]
            break
        i += 1

    return hop_rtts


def compute_increments(
    hop_rtts: list[tuple[int, float]],
) -> list[tuple[int, float, float]]:
    hop_rtts = sorted(hop_rtts, key=lambda x: x[0])
    increments = []
    prev = 0.0
    for hop_idx, rtt in hop_rtts:
        inc = max(0.0, rtt - prev)
        increments.append((hop_idx, rtt, inc))
        if rtt != 0.0:
            prev = rtt
    return increments


def get_ping_stats(target: str, count: int = 100, interval: float = 0.01) -> dict | None:
    """
    Pings a target and returns statistics.
    Returns: dict {'min': float, 'avg': float, 'max': float} or None if failed.
    """
    import re
    cmd = ["ping", "-c", str(count), "-i", str(interval), target]
    
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=count * interval + 10
        )
        
        if result.returncode != 0:
            return None

        pattern = r"rtt min/avg/max/mdev = ([0-9.]+)/([0-9.]+)/([0-9.]+)/[0-9.]+ ms"
        match = re.search(pattern, result.stdout)
        
        if match:
            return {
                'min': float(match.group(1)),
                'avg': float(match.group(2)),
                'max': float(match.group(3))
            }
        else:
            return None

    except Exception as e:
        print(f"Error executing ping subprocess for {target}: {e}")
        return None


def save_stacked_bar(data: list[dict], out_path: Path) -> None:
    labels = [d["host"] for d in data]
    max_hops = max((len(d["increments"]) for d in data), default=0)
    bottoms = [0.0] * len(data)

    fig, ax = plt.subplots(figsize=(10, 6))
    colors = plt.cm.plasma(
        [0.35 + (0.5 * i / max(1, max_hops - 1)) for i in range(max_hops)]
    )
    for hop_i in range(1, max_hops + 1):
        vals = []
        for d in data:
            inc = 0.0
            for hop_idx, _rtt, inc_val in d["increments"]:
                if hop_idx == hop_i:
                    inc = inc_val
                    break
            vals.append(inc)
        ax.bar(
            labels, vals, bottom=bottoms, label=f"hop {hop_i}", color=colors[hop_i - 1]
        )
        bottoms = [b + v for b, v in zip(bottoms, vals)]
    ax.set_ylabel("Incremental RTT (ms)")
    ax.set_title("Latency Breakdown by Hop (Stacked)")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right")
    max_total = max(bottoms) if bottoms else 0.0
    ax.set_ylim(0, max_total * 1.1 if max_total > 0 else 1.0)
    if max_hops > 0 and max_hops <= 12:
        ax.legend(loc="upper left", fontsize="small")
    fig.tight_layout()
    fig.savefig(out_path, format="pdf")
    plt.close(fig)


def save_scatter(data: list[dict], out_path: Path) -> None:
    hop_counts = []
    ping_rtts = []
    labels = []
    for d in data:
        if not d["increments"] or "ping_rtt" not in d:
            continue
        hop_counts.append(len(d["increments"]))
        ping_rtts.append(d["ping_rtt"])
        labels.append(d["host"])

    plt.figure(figsize=(8, 6))
    plt.scatter(hop_counts, ping_rtts)
    for x, y, label in zip(hop_counts, ping_rtts, labels):
        plt.annotate(label, (x, y), fontsize="x-small", alpha=0.7)
    plt.xlabel("Hop Count")
    plt.ylabel("Ping RTT (ms)")
    plt.title("Hop Count vs Ping RTT")
    plt.tight_layout()
    plt.savefig(out_path, format="pdf")
    plt.close()


def save_csv(data: list[dict], out_path: Path) -> None:
    with out_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["host", "hop_index", "rtt_ms", "increment_ms"])
        for d in data:
            for hop_idx, rtt, inc in d["increments"]:
                writer.writerow([d["host"], hop_idx, f"{rtt:.3f}", f"{inc:.3f}"])


def main() -> None:
    print(
        "Note: Extra hops at end of traceroute that are all unreachable are removed from data."
    )
    parser = argparse.ArgumentParser(description="Latency breakdown via traceroute.")
    parser.add_argument("--input", default="listed_iperf3_servers.csv")
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=3)
    args = parser.parse_args()

    hosts = read_hosts(Path(args.input))
    if len(hosts) < args.count:
        raise SystemExit("Not enough hosts in input file.")

    #selected = random.sample(hosts, args.count)
    # we coded random sampling but will select 5 to use via Piazza post 27
    selected = ["speedtest.kamel.network", "speedtest.keff.org", "lg.gigahost.no", "speedtest.sfo12.us.leaseweb.net", "atl.speedtest.clouvider.net"]

    data = []
    for host in selected:
        hop_rtts = run_traceroute(host, args.timeout)
        increments = compute_increments(hop_rtts)
        ping_stats = get_ping_stats(host)
        ping_rtt = ping_stats['avg'] if ping_stats else None
        data.append({"host": host, "increments": increments, "ping_rtt": ping_rtt})

    Path("part2_outputs").mkdir(exist_ok=True)
    save_csv(data, Path("part2_outputs/latency_breakdown.csv"))
    save_stacked_bar(data, Path("part2_outputs/latency_breakdown_stacked.pdf"))
    save_scatter(data, Path("part2_outputs/hopcount_vs_rtt.pdf"))

    print("Selected hosts:")
    for s in selected:
        print(f"  {s}")
    print("")

    for d in data:
        hops = len(d["increments"])
        last_rtt = None
        if hops:
            last_rtt = d["increments"][-1][1]
        ping_rtt = d.get("ping_rtt")
        ping_rtt_str = f"{ping_rtt:.3f}" if ping_rtt else "N/A"
        print(f"{d['host']}: hops={hops} traceroute_rtt_ms={last_rtt} ping_rtt_ms={ping_rtt_str}")
        for hop_idx, rtt, inc in d["increments"]:
            print(f"  hop {hop_idx}: rtt_ms={rtt:.3f} incremental_ms={inc:.3f}")
        print("")
    print("Outputs written to ./part2_outputs")


if __name__ == "__main__":
    main()
