"""One-shot Broadcast benchmark runner for Assignment 5."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

from benchmark_common import (
    BASE_DIR,
    DEFAULT_PLOTS_DIR,
    GLOO_BACKEND,
    build_broadcast_tensor,
    ensure_directory,
    format_bytes,
    plot_message_size_results,
    plot_rank_scaling_results,
    pretty_algorithm_name,
    validate_broadcast_output,
)
from distributed_utils import cleanup_process_group, get_rank_metadata, setup_process_group


ALGORITHMS = ["binary_tree", "binomial_tree"]
MESSAGE_SIZES_BYTES = [
    1024,
    4096,
    16384,
    65536,
    262144,
    1048576,
    4194304,
    8388608,
    # 16777216,
    # 33554432,
    # 67108864,
]
RANK_COUNTS = [2, 4, 8, 16]
WARMUP_ITERATIONS = 2
TIMED_ITERATIONS = 5
SOURCE_RANK = 0
FIXED_RANK_FOR_MESSAGE_SWEEP = 8
FIXED_MESSAGE_SIZE_FOR_RANK_SWEEP_BYTES = 1048576
MESSAGE_SIZE_PLOT_PATH = DEFAULT_PLOTS_DIR / "broadcast_vs_message_size.png"
RANK_SCALING_PLOT_PATH = DEFAULT_PLOTS_DIR / "broadcast_vs_ranks.png"


def parse_int_list(raw_value: str) -> list[int]:
    """Parse a comma-separated positive integer list from the command line."""
    values = [int(value.strip()) for value in raw_value.split(",") if value.strip()]
    if not values:
        raise argparse.ArgumentTypeError("Expected at least one integer.")
    if any(value <= 0 for value in values):
        raise argparse.ArgumentTypeError("Values must be positive integers.")
    return values


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Broadcast benchmarks with the PyTorch gloo backend."
    )
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--algorithm", choices=ALGORITHMS, help=argparse.SUPPRESS)
    parser.add_argument("--message-size-bytes", type=int, help=argparse.SUPPRESS)
    parser.add_argument(
        "--warmup-iterations",
        type=int,
        default=WARMUP_ITERATIONS,
        help="Warmup iterations before timing.",
    )
    parser.add_argument(
        "--timed-iterations",
        type=int,
        default=TIMED_ITERATIONS,
        help="Timed iterations per benchmark case.",
    )
    parser.add_argument(
        "--message-sizes-bytes",
        type=parse_int_list,
        default=MESSAGE_SIZES_BYTES,
        help="Comma-separated message sizes for the message-size sweep.",
    )
    parser.add_argument(
        "--rank-counts",
        type=parse_int_list,
        default=RANK_COUNTS,
        help="Comma-separated rank counts for the rank-scaling sweep.",
    )
    parser.add_argument(
        "--fixed-rank",
        type=int,
        default=FIXED_RANK_FOR_MESSAGE_SWEEP,
        help="Rank count used for the message-size sweep.",
    )
    parser.add_argument(
        "--fixed-message-size-bytes",
        type=int,
        default=FIXED_MESSAGE_SIZE_FOR_RANK_SWEEP_BYTES,
        help="Message size used for the rank-scaling sweep.",
    )
    parser.add_argument(
        "--source-rank",
        type=int,
        default=SOURCE_RANK,
        help="Broadcast source rank.",
    )
    return parser


def get_broadcast_algorithm(name: str):
    if name == "binary_tree":
        from algorithms.broadcast_binary_tree import broadcast_binary_tree

        return broadcast_binary_tree
    if name == "binomial_tree":
        from algorithms.broadcast_binomial_tree import broadcast_binomial_tree

        return broadcast_binomial_tree
    raise ValueError(f"Unknown Broadcast algorithm: {name}")


def parse_worker_result(stdout: str) -> dict:
    """Read the final JSON payload printed by rank 0."""
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    raise RuntimeError("Worker did not print a benchmark result.")


def run_worker(args: argparse.Namespace) -> None:
    import torch
    import torch.distributed as dist

    algorithm = get_broadcast_algorithm(args.algorithm)

    setup_process_group(backend=GLOO_BACKEND)
    try:
        metadata = get_rank_metadata()
        rank = metadata["rank"]
        world_size = metadata["world_size"]

        if not 0 <= args.source_rank < world_size:
            raise ValueError(
                f"Broadcast source rank {args.source_rank} is outside world size "
                f"{world_size}."
            )

        torch.set_num_threads(1)

        tensor = build_broadcast_tensor(
            rank,
            args.source_rank,
            args.message_size_bytes,
        )

        dist.barrier()
        algorithm(tensor, src=args.source_rank)

        is_valid = validate_broadcast_output(
            tensor,
            args.source_rank,
            args.message_size_bytes,
        )
        validation_tensor = torch.tensor(1 if is_valid else 0, dtype=torch.int64)
        dist.all_reduce(validation_tensor, op=dist.ReduceOp.MIN)
        if validation_tensor.item() != 1:
            raise RuntimeError(
                f"Validation failed for {args.algorithm} "
                f"with world_size={world_size}, source_rank={args.source_rank}, "
                f"and message_size_bytes={args.message_size_bytes}."
            )

        for _ in range(args.warmup_iterations):
            tensor = build_broadcast_tensor(
                rank,
                args.source_rank,
                args.message_size_bytes,
            )
            dist.barrier()
            algorithm(tensor, src=args.source_rank)

        timings_ms = []
        for _ in range(args.timed_iterations):
            tensor = build_broadcast_tensor(
                rank,
                args.source_rank,
                args.message_size_bytes,
            )
            dist.barrier()
            start_time = time.perf_counter()
            algorithm(tensor, src=args.source_rank)
            elapsed_seconds = time.perf_counter() - start_time

            elapsed_tensor = torch.tensor(elapsed_seconds, dtype=torch.float64)
            dist.all_reduce(elapsed_tensor, op=dist.ReduceOp.MAX)
            timings_ms.append(elapsed_tensor.item() * 1000.0)

        if rank == 0:
            result = {
                "collective": "broadcast",
                "algorithm": args.algorithm,
                "world_size": world_size,
                "source_rank": args.source_rank,
                "message_size_bytes": args.message_size_bytes,
                "timings_ms": timings_ms,
                "average_time_ms": statistics.mean(timings_ms),
            }
            print(json.dumps(result))
    finally:
        cleanup_process_group()


def launch_worker(
    algorithm: str,
    message_size_bytes: int,
    world_size: int,
    source_rank: int,
    warmup_iterations: int,
    timed_iterations: int,
) -> dict:
    command = [
        sys.executable,
        "-m",
        "torch.distributed.run",
        "--standalone",
        f"--nproc_per_node={world_size}",
        str(Path(__file__).resolve()),
        "--worker",
        "--algorithm",
        algorithm,
        "--message-size-bytes",
        str(message_size_bytes),
        "--source-rank",
        str(source_rank),
        "--warmup-iterations",
        str(warmup_iterations),
        "--timed-iterations",
        str(timed_iterations),
    ]

    env = os.environ.copy()
    env.setdefault("OMP_NUM_THREADS", "1")

    completed = subprocess.run(
        command,
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    if completed.returncode != 0:
        raise RuntimeError(
            "Distributed benchmark failed.\n"
            f"Command: {' '.join(command)}\n"
            f"STDOUT:\n{completed.stdout}\n"
            f"STDERR:\n{completed.stderr}"
        )

    return parse_worker_result(completed.stdout)


def plot_message_size_sweep(
    message_sweep_results: dict,
    message_sizes_bytes: list[int],
) -> None:
    plot_message_size_results(
        results=message_sweep_results["results"],
        algorithms=ALGORITHMS,
        message_sizes_bytes=message_sizes_bytes,
        fixed_rank=message_sweep_results["fixed_rank"],
        collective_name="Broadcast",
        output_path=MESSAGE_SIZE_PLOT_PATH,
    )


def plot_rank_scaling_sweep(rank_scaling_results: dict, rank_counts: list[int]) -> None:
    plot_rank_scaling_results(
        results=rank_scaling_results["results"],
        algorithms=ALGORITHMS,
        rank_counts=rank_counts,
        fixed_message_size_bytes=rank_scaling_results["fixed_message_size_bytes"],
        collective_name="Broadcast",
        output_path=RANK_SCALING_PLOT_PATH,
    )


def run_message_size_sweep(args: argparse.Namespace) -> dict:
    print("Running Broadcast message-size sweep")
    print(f"fixed ranks: {args.fixed_rank}")
    print(f"source rank: {args.source_rank}")
    print(flush=True)

    results = []
    for algorithm in ALGORITHMS:
        for message_size_bytes in args.message_sizes_bytes:
            print(
                "  starting "
                f"{algorithm:20s} {format_bytes(message_size_bytes):>8s} "
                f"at {args.fixed_rank} ranks",
                flush=True,
            )
            result = launch_worker(
                algorithm=algorithm,
                message_size_bytes=message_size_bytes,
                world_size=args.fixed_rank,
                source_rank=args.source_rank,
                warmup_iterations=args.warmup_iterations,
                timed_iterations=args.timed_iterations,
            )
            results.append(result)
            print(
                f"  {algorithm:20s} {format_bytes(message_size_bytes):>8s} "
                f"-> {result['average_time_ms']:.3f} ms",
                flush=True,
            )

    print(flush=True)
    return {
        "fixed_rank": args.fixed_rank,
        "source_rank": args.source_rank,
        "results": results,
    }


def run_rank_scaling_sweep(args: argparse.Namespace) -> dict:
    print("Running Broadcast rank-scaling sweep")
    print(f"fixed message size: {format_bytes(args.fixed_message_size_bytes)}")
    print(f"source rank: {args.source_rank}")
    print(flush=True)

    results = []
    for algorithm in ALGORITHMS:
        for world_size in args.rank_counts:
            print(
                "  starting "
                f"{algorithm:20s} {world_size:>8d} ranks "
                f"at {format_bytes(args.fixed_message_size_bytes)}",
                flush=True,
            )
            result = launch_worker(
                algorithm=algorithm,
                message_size_bytes=args.fixed_message_size_bytes,
                world_size=world_size,
                source_rank=args.source_rank,
                warmup_iterations=args.warmup_iterations,
                timed_iterations=args.timed_iterations,
            )
            results.append(result)
            print(
                f"  {algorithm:20s} {world_size:>8d} ranks "
                f"-> {result['average_time_ms']:.3f} ms",
                flush=True,
            )

    print(flush=True)
    return {
        "fixed_message_size_bytes": args.fixed_message_size_bytes,
        "source_rank": args.source_rank,
        "results": results,
    }


def finalize_results(
    message_sweep_results: dict,
    rank_scaling_results: dict,
    message_sizes_bytes: list[int],
    rank_counts: list[int],
) -> None:
    ensure_directory(DEFAULT_PLOTS_DIR)
    plot_message_size_sweep(message_sweep_results, message_sizes_bytes)
    plot_rank_scaling_sweep(rank_scaling_results, rank_counts)

    print("Generated plots:")
    print(f"  - {MESSAGE_SIZE_PLOT_PATH}", flush=True)
    print(f"  - {RANK_SCALING_PLOT_PATH}", flush=True)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.worker:
        run_worker(args)
        return

    print("Assignment 5 Broadcast benchmark", flush=True)
    print(
        "algorithms: "
        + ", ".join(pretty_algorithm_name(algorithm) for algorithm in ALGORITHMS),
        flush=True,
    )
    print(
        "message sizes: "
        + ", ".join(format_bytes(message_size) for message_size in args.message_sizes_bytes),
        flush=True,
    )
    print(
        "rank counts: " + ", ".join(str(rank) for rank in args.rank_counts),
        flush=True,
    )
    print(flush=True)

    message_sweep_results = run_message_size_sweep(args)
    rank_scaling_results = run_rank_scaling_sweep(args)
    finalize_results(
        message_sweep_results,
        rank_scaling_results,
        args.message_sizes_bytes,
        args.rank_counts,
    )


if __name__ == "__main__":
    main()
