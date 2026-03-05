#!/usr/bin/env python3
import argparse
import csv
import json
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

# Reuse the Assignment 2 socket application directly.
THIS_DIR = Path(__file__).resolve().parent
ASSIGNMENT2_DIR = THIS_DIR.parent / "Assignment_2"
if str(ASSIGNMENT2_DIR) not in sys.path:
    sys.path.insert(0, str(ASSIGNMENT2_DIR))

from iperf3_client import Iperf3Client  # noqa: E402


@dataclass
class Sample:
    timestamp_s: float
    goodput_bps: float
    throughput_mbps: float
    rtt_ms: float
    snd_cwnd: int
    total_retrans: int
    retrans_delta: int
    loss_events_per_s: float


def to_samples(tcp_stats: List[dict]) -> List[Sample]:
    samples: List[Sample] = []
    last_total_retrans = 0
    last_timestamp = 0.0

    for row in tcp_stats:
        ts = float(row.get("time", 0.0))
        goodput_bps = float(row.get("goodput_bps", 0.0))
        total_retrans = int(row.get("total_retrans", 0))

        retrans_delta = max(0, total_retrans - last_total_retrans)
        interval = ts - last_timestamp
        loss_events_per_s = (retrans_delta / interval) if interval > 0 else 0.0

        samples.append(
            Sample(
                timestamp_s=ts,
                goodput_bps=goodput_bps,
                throughput_mbps=goodput_bps / 1_000_000.0,
                rtt_ms=float(row.get("rtt_ms", 0.0)),
                snd_cwnd=int(row.get("snd_cwnd", 0)),
                total_retrans=total_retrans,
                retrans_delta=retrans_delta,
                loss_events_per_s=loss_events_per_s,
            )
        )

        last_total_retrans = total_retrans
        last_timestamp = ts

    return samples


def write_samples_csv(path: Path, samples: List[Sample]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "timestamp_s",
                "goodput_bps",
                "throughput_mbps",
                "rtt_ms",
                "snd_cwnd",
                "total_retrans",
                "retrans_delta",
                "loss_events_per_s",
            ]
        )
        for s in samples:
            writer.writerow(
                [
                    f"{s.timestamp_s:.6f}",
                    f"{s.goodput_bps:.2f}",
                    f"{s.throughput_mbps:.3f}",
                    f"{s.rtt_ms:.3f}",
                    s.snd_cwnd,
                    s.total_retrans,
                    s.retrans_delta,
                    f"{s.loss_events_per_s:.3f}",
                ]
            )


def summarize_throughput(samples: List[Sample]) -> Dict[str, float]:
    goodputs_mbps = [s.throughput_mbps for s in samples]
    avg_rtt_ms = statistics.mean([s.rtt_ms for s in samples])
    total_loss_events = float(sum(s.retrans_delta for s in samples))
    return {
        "mean_mbps": statistics.mean(goodputs_mbps),
        "median_mbps": statistics.median(goodputs_mbps),
        "min_mbps": min(goodputs_mbps),
        "max_mbps": max(goodputs_mbps),
        "avg_rtt_ms": avg_rtt_ms,
        "total_loss_events": total_loss_events,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Assignment 3 Option 1 test runner")
    parser.add_argument("--server", required=True, help="iPerf3 server hostname or IP")
    parser.add_argument("--port", type=int, default=5201, help="iPerf3 server port")
    parser.add_argument("--duration", type=int, default=10, help="Duration (seconds) per run")
    parser.add_argument("--runs", type=int, default=3, help="Runs per congestion-control algorithm")
    parser.add_argument(
        "--algos",
        nargs="+",
        default=["dummycc", "cubic", "reno"],
        help="Algorithms to test in order",
    )
    parser.add_argument("--output-dir", default="results", help="Output folder under Assignment_3")
    args = parser.parse_args()

    output_dir = THIS_DIR / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    all_results: Dict[str, List[Dict[str, float | int | str]]] = {algo: [] for algo in args.algos}

    for algo in args.algos:
        print(f"\n=== Testing {algo} ===")
        for run_id in range(1, args.runs + 1):
            print(f"[{algo}] Run {run_id}/{args.runs}...")

            client = Iperf3Client(
                server_ip=args.server,
                server_port=args.port,
                duration=args.duration,
                cc_algo=algo,
            )
            ok, tcp_stats = client.run()
            if not ok:
                reason = "connection/test failed"
                print(f"[{algo}] run {run_id} failed: {reason}")
                all_results[algo].append({"run": run_id, "status": "failed", "reason": reason})
                continue

            samples = to_samples(tcp_stats)
            if not samples:
                reason = "no samples collected"
                print(f"[{algo}] run {run_id} failed: {reason}")
                all_results[algo].append({"run": run_id, "status": "failed", "reason": reason})
                continue

            run_summary = summarize_throughput(samples)
            all_results[algo].append({"run": run_id, "status": "ok", **run_summary})

            csv_path = output_dir / f"{algo}_run{run_id}.csv"
            write_samples_csv(csv_path, samples)
            print(
                f"[{algo}] run {run_id} mean={run_summary['mean_mbps']:.2f} Mbps, "
                f"median={run_summary['median_mbps']:.2f} Mbps"
            )

    summary_path = output_dir / "summary.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)

    print("\n=== Aggregate comparison (mean of successful runs) ===")
    for algo, runs in all_results.items():
        successful_means = [float(r["mean_mbps"]) for r in runs if r.get("status") == "ok"]
        if successful_means:
            print(f"{algo:>8}: {statistics.mean(successful_means):.2f} Mbps")
        else:
            print(f"{algo:>8}: no successful runs")

    print(f"\nSaved per-run CSV files and summary to: {output_dir}")


if __name__ == "__main__":
    main()
