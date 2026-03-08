#!/usr/bin/env python3
import argparse
import csv
import io
import statistics
import sys
import time
from contextlib import redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

# Reuse the Assignment 2 socket application directly.
THIS_DIR = Path(__file__).resolve().parent
ASSIGNMENT2_DIR = THIS_DIR.parent / "Assignment_2"
if str(ASSIGNMENT2_DIR) not in sys.path:
    sys.path.insert(0, str(ASSIGNMENT2_DIR))

from iperf3_client import Iperf3Client


@dataclass
class Sample:
    timestamp_s: float
    goodput_mbps: float
    rtt_ms: float
    retransmits: Optional[int]
    cwnd: Optional[int]


def _first_number(row: dict, keys: List[str]) -> Optional[float]:
    for key in keys:
        if key in row and row[key] is not None:
            try:
                return float(row[key])
            except (TypeError, ValueError):
                continue
    return None


def to_samples(tcp_stats: List[dict]) -> List[Sample]:
    samples: List[Sample] = []
    last_total_retrans = 0.0

    for row in tcp_stats:
        ts = float(row.get("time", 0.0))
        goodput_mbps = float(row.get("goodput_bps", 0.0)) / 1_000_000

        retransmits_raw = _first_number(row, ["retransmits", "total_retrans", "retrans_total"])
        cwnd_raw = _first_number(row, ["snd_cwnd", "cwnd"])
        if retransmits_raw is not None:
            total_retrans = float(retransmits_raw)
            retransmits = int(max(0.0, total_retrans - last_total_retrans))
            last_total_retrans = total_retrans
        else:
            retransmits = None
        cwnd = int(cwnd_raw) if cwnd_raw is not None else None

        samples.append(
            Sample(
                timestamp_s=ts,
                goodput_mbps=goodput_mbps,
                rtt_ms=float(row.get("rtt_ms", 0.0)),
                retransmits=retransmits,
                cwnd=cwnd,
            )
        )

    return samples


def write_samples_csv(path: Path, samples: List[Sample]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "timestamp_s",
                "goodput_mbps",
                "rtt_ms",
                "retransmits",
                "cwnd",
            ]
        )
        for s in samples:
            writer.writerow(
                [
                    f"{s.timestamp_s:.2f}",
                    f"{s.goodput_mbps:.2f}",
                    f"{s.rtt_ms:.2f}",
                    "" if s.retransmits is None else s.retransmits,
                    "" if s.cwnd is None else s.cwnd,
                ]
            )


def summarize_run(samples: List[Sample]) -> Dict[str, float]:
    goodputs = [s.goodput_mbps for s in samples]
    rtts = [s.rtt_ms for s in samples]
    retrans = [s.retransmits for s in samples if s.retransmits is not None]
    cwnds = [s.cwnd for s in samples if s.cwnd is not None]
    return {
        "avg_goodput_mbps": statistics.mean(goodputs) if goodputs else 0.0,
        "avg_rtt_ms": statistics.mean(rtts) if rtts else 0.0,
        "avg_retransmits": statistics.mean(retrans) if retrans else 0.0,
        "total_retransmits": float(sum(retrans)) if retrans else 0.0,
        "avg_cwnd": statistics.mean(cwnds) if cwnds else 0.0,
    }


def summarize_run_csv(path: Path) -> Dict[str, float]:
    samples: List[Sample] = []
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            samples.append(
                Sample(
                    timestamp_s=float(row["timestamp_s"]),
                    goodput_mbps=float(row["goodput_mbps"]),
                    rtt_ms=float(row["rtt_ms"]),
                    retransmits=int(row["retransmits"]) if row["retransmits"] != "" else None,
                    cwnd=int(row["cwnd"]) if row["cwnd"] != "" else None,
                )
            )
    return summarize_run(samples)


def collect_results_from_run_csvs(output_dir: Path) -> tuple[Dict[str, List[Dict[str, float | str]]], Dict[str, List[float]]]:
    all_results: Dict[str, List[Dict[str, float | str]]] = {}
    algo_goodputs: Dict[str, List[float]] = {}

    for csv_path in sorted(output_dir.glob("*_run*.csv")):
        stem = csv_path.stem
        if "_run" not in stem:
            continue
        algo, _ = stem.rsplit("_run", 1)
        all_results.setdefault(algo, [])
        algo_goodputs.setdefault(algo, [])

        run_summary = summarize_run_csv(csv_path)
        all_results[algo].append({"status": "ok", **run_summary})

        with csv_path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                algo_goodputs[algo].append(float(row["goodput_mbps"]))

    return all_results, algo_goodputs


def load_existing_failed_counts(path: Path) -> Dict[str, int]:
    failed_counts: Dict[str, int] = {}
    if not path.exists():
        return failed_counts

    try:
        with path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                algo = row.get("algo", "")
                failed = row.get("failed_runs", "")
                if algo and failed != "":
                    failed_counts[algo] = int(float(failed))
    except Exception:
        return {}

    return failed_counts


def percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    rank = (p / 100.0) * (len(sorted_vals) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(sorted_vals) - 1)
    weight = rank - lo
    return sorted_vals[lo] * (1.0 - weight) + sorted_vals[hi] * weight


def write_algo_comparison_csv(
    path: Path,
    all_results: Dict[str, List[Dict[str, float | str]]],
    algo_goodputs: Dict[str, List[float]],
    failed_counts: Dict[str, int],
) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "algo",
                "successful_runs",
                "failed_runs",
                "min_goodput_mbps",
                "median_goodput_mbps",
                "avg_goodput_mbps",
                "p95_goodput_mbps",
                "avg_rtt_ms",
                "avg_retransmits",
                "total_retransmits",
                "avg_cwnd",
            ]
        )

        for algo in sorted(set(all_results.keys()) | set(failed_counts.keys())):
            runs = all_results.get(algo, [])
            successful = [r for r in runs if r["status"] == "ok"]
            failed_count = failed_counts.get(algo, 0)
            goodputs = algo_goodputs.get(algo, [])
            if successful:
                writer.writerow(
                    [
                        algo,
                        len(successful),
                        failed_count,
                        f"{min(goodputs):.2f}" if goodputs else "",
                        f"{statistics.median(goodputs):.2f}" if goodputs else "",
                        f"{statistics.mean(goodputs):.2f}" if goodputs else "",
                        f"{percentile(goodputs, 95.0):.2f}" if goodputs else "",
                        f"{statistics.mean(float(r['avg_rtt_ms']) for r in successful):.2f}",
                        f"{statistics.mean(float(r['avg_retransmits']) for r in successful):.2f}",
                        int(sum(float(r["total_retransmits"]) for r in successful)),
                        f"{statistics.mean(float(r['avg_cwnd']) for r in successful):.2f}",
                    ]
                )
            else:
                writer.writerow([algo, 0, failed_count, "", "", "", "", "", "", "", ""])


def main() -> None:
    parser = argparse.ArgumentParser(description="Assignment 3 Option 1 test runner")
    parser.add_argument("--server", required=True, help="iPerf3 server hostname or IP")
    parser.add_argument("--port", type=int, default=5201, help="iPerf3 server port")
    parser.add_argument("--duration", type=int, default=10, help="Duration (seconds) per run")
    parser.add_argument("--runs", type=int, default=1, help="Runs per congestion-control algorithm")
    parser.add_argument("--delay-between-runs", type=float, default=10.0, help="Sleep between runs (seconds)")
    parser.add_argument(
        "--algos",
        nargs="+",
        default=["our_cc", "cubic", "reno"],
        help="Algorithms to test in order",
    )
    parser.add_argument("--output-dir", default="results", help="Output folder under Assignment_3")
    args = parser.parse_args()

    output_dir = THIS_DIR / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    failed_counts_this_invocation: Dict[str, int] = {algo: 0 for algo in args.algos}

    for algo in args.algos:
        for run_id in range(1, args.runs + 1):
            client = Iperf3Client(
                server_ip=args.server,
                server_port=args.port,
                duration=args.duration,
                cc_algo=algo,
            )
            with redirect_stdout(io.StringIO()):
                ok, tcp_stats = client.run()
            samples: List[Sample] = to_samples(tcp_stats) if ok else []

            if not ok or not samples:
                print(f"{args.server} {algo} run {run_id}: failed")
                failed_counts_this_invocation[algo] += 1
                if args.delay_between_runs > 0:
                    time.sleep(args.delay_between_runs)
                continue

            csv_path = output_dir / f"{algo}_run{run_id}.csv"
            write_samples_csv(csv_path, samples)
            print(f"{args.server} {algo} run {run_id}: succeeded")
            if args.delay_between_runs > 0:
                time.sleep(args.delay_between_runs)

            
    comparison_path = output_dir / "algo_comparison.csv"
    previous_failed_counts = load_existing_failed_counts(comparison_path)
    merged_failed_counts = dict(previous_failed_counts)
    for algo, count in failed_counts_this_invocation.items():
        merged_failed_counts[algo] = count

    all_results, algo_goodputs = collect_results_from_run_csvs(output_dir)
    write_algo_comparison_csv(comparison_path, all_results, algo_goodputs, merged_failed_counts)


if __name__ == "__main__":
    main()
