"""One-shot AllGather benchmark runner for Assignment 5."""

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
    build_input_tensor,
    ensure_directory,
    format_bytes,
    is_power_of_two,
    plot_message_size_results,
    plot_rank_scaling_results,
    pretty_algorithm_name,
    validate_allgather_output,
)
from distributed_utils import cleanup_process_group, get_rank_metadata, setup_process_group


# hardcoded experiment config
ALGORITHMS = ["ring", "recursive_doubling", "swing"]
MESSAGE_SIZES_BYTES = [
    1024,
    4096,
    16384,
    65536,
    262144,
    1048576,
    4194304,
    8388608,
    #16777216,
    #33554432,
    #67108864,
]
# The assignment asks us to reach at least 8 ranks. Higher counts are optional
# and can make local Docker runs feel stalled on limited CPUs.
RANK_COUNTS = [2, 4, 8, 16]
WARMUP_ITERATIONS = 2
TIMED_ITERATIONS = 5
FIXED_RANK_FOR_MESSAGE_SWEEP = 8
FIXED_MESSAGE_SIZE_FOR_RANK_SWEEP_BYTES = 1048576
MESSAGE_SIZE_PLOT_PATH = DEFAULT_PLOTS_DIR / "allgather_vs_message_size.png"
RANK_SCALING_PLOT_PATH = DEFAULT_PLOTS_DIR / "allgather_vs_ranks.png"


def build_parser() -> argparse.ArgumentParser:
    """Only parse hidden internal arguments used by distributed worker processes."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--algorithm", choices=ALGORITHMS, help=argparse.SUPPRESS)
    parser.add_argument("--message-size-bytes", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--warmup-iterations", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--timed-iterations", type=int, help=argparse.SUPPRESS)
    return parser


# algorithm selection
def get_allgather_algorithm(name: str):
    if name == "ring":
        from algorithms.allgather_ring import allgather_ring

        return allgather_ring
    if name == "recursive_doubling":
        from algorithms.allgather_recursive_doubling import allgather_recursive_doubling

        return allgather_recursive_doubling
    if name == "swing":
        from algorithms.allgather_swing import allgather_swing

        return allgather_swing


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


# function that each node actually runs to perform the benchmark
def run_worker(args: argparse.Namespace) -> None:
    import torch
    import torch.distributed as dist

    algorithm = get_allgather_algorithm(args.algorithm)

    setup_process_group(backend=GLOO_BACKEND) # Initializes PyTorch's distributed communication
    try:
        metadata = get_rank_metadata()
        rank = metadata["rank"]
        world_size = metadata["world_size"]

        torch.set_num_threads(1)

        input_tensor = build_input_tensor(rank, args.message_size_bytes) # each node creates its unique data
        # will contain the gathered results from all ranks after the AllGather completes
        output_buffer = torch.empty(
            (world_size, args.message_size_bytes),
            dtype=input_tensor.dtype,
        )


        ##### runs algo once to test if it works and to populate the output buffer for validation #####
        dist.barrier()  # synchronize before starting the benchmark
        algorithm(input_tensor, output_buffer)

        # verify everyone got correct data
        is_valid = validate_allgather_output(output_buffer, args.message_size_bytes)
        validation_tensor = torch.tensor(1 if is_valid else 0, dtype=torch.int64)
        dist.all_reduce(validation_tensor, op=dist.ReduceOp.MIN)
        if validation_tensor.item() != 1:
            raise RuntimeError(
                f"Validation failed for {args.algorithm} "
                f"with world_size={world_size} and "
                f"message_size_bytes={args.message_size_bytes}."
            )
        ##### runs algo once to test if it works and to populate the output buffer for validation #####


        ##### warmup to fill the cache and such #####
        for _ in range(args.warmup_iterations):
            dist.barrier()
            algorithm(input_tensor, output_buffer)
        ##### warmup to fill the cache and such #####


        timings_ms = []
        for _ in range(args.timed_iterations):
            dist.barrier()
            start_time = time.perf_counter()
            algorithm(input_tensor, output_buffer)
            elapsed_seconds = time.perf_counter() - start_time

            # Get MAX time across all ranks (slowest rank determines actual time)
            elapsed_tensor = torch.tensor(elapsed_seconds, dtype=torch.float64)
            dist.all_reduce(elapsed_tensor, op=dist.ReduceOp.MAX)
            timings_ms.append(elapsed_tensor.item() * 1000.0)

        if rank == 0:
            result = {
                "algorithm": args.algorithm,
                "world_size": world_size,
                "message_size_bytes": args.message_size_bytes,
                "timings_ms": timings_ms,
                "average_time_ms": statistics.mean(timings_ms),
            }
            print(json.dumps(result))
    finally:
        cleanup_process_group()


# distributed worker launcher
def launch_worker(algorithm: str, message_size_bytes: int, world_size: int) -> dict:
    if algorithm in {"recursive_doubling", "swing"} and not is_power_of_two(world_size):
        raise ValueError(
            f"{pretty_algorithm_name(algorithm)} requires a power-of-two world size. "
            f"Received {world_size}."
        )

    # Launch one worker process per rank, each running this same script in worker mode.
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
        "--warmup-iterations",
        str(WARMUP_ITERATIONS),
        "--timed-iterations",
        str(TIMED_ITERATIONS),
    ]

    env = os.environ.copy() 
    env.setdefault("OMP_NUM_THREADS", "1") # limit each process to one thread

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

    # Extract the JSON timing payload printed by rank 0.
    return parse_worker_result(completed.stdout) 


def plot_message_size_sweep(message_sweep_results: dict) -> None:
    plot_message_size_results(
        results=message_sweep_results["results"],
        algorithms=ALGORITHMS,
        message_sizes_bytes=MESSAGE_SIZES_BYTES,
        fixed_rank=message_sweep_results["fixed_rank"],
        collective_name="AllGather",
        output_path=MESSAGE_SIZE_PLOT_PATH,
    )


def plot_rank_scaling_sweep(rank_scaling_results: dict) -> None:
    plot_rank_scaling_results(
        results=rank_scaling_results["results"],
        algorithms=ALGORITHMS,
        rank_counts=RANK_COUNTS,
        fixed_message_size_bytes=rank_scaling_results["fixed_message_size_bytes"],
        collective_name="AllGather",
        output_path=RANK_SCALING_PLOT_PATH,
    )


# message-size sweep
def run_message_size_sweep() -> dict:
    print("Running AllGather message-size sweep")
    print(f"fixed ranks: {FIXED_RANK_FOR_MESSAGE_SWEEP}")
    print(flush=True)

    results = []
    for algorithm in ALGORITHMS: # ring, recursive_doubling, swing
        for message_size_bytes in MESSAGE_SIZES_BYTES:
            print(
                "  starting "
                f"{algorithm:20s} {format_bytes(message_size_bytes):>8s} "
                f"at {FIXED_RANK_FOR_MESSAGE_SWEEP} ranks",
                flush=True,
            )
            result = launch_worker(
                algorithm=algorithm,
                message_size_bytes=message_size_bytes,
                world_size=FIXED_RANK_FOR_MESSAGE_SWEEP, # number of processes is fixed at 8 for this sweep
            )
            results.append(result)
            print(
                f"  {algorithm:20s} {format_bytes(message_size_bytes):>8s} "
                f"-> {result['average_time_ms']:.3f} ms",
                flush=True,
            )

    print(flush=True)
    return {
        "fixed_rank": FIXED_RANK_FOR_MESSAGE_SWEEP,
        "results": results,
    }


# rank-scaling sweep
def run_rank_scaling_sweep() -> dict:
    print("Running AllGather rank-scaling sweep")
    print(f"fixed message size: {format_bytes(FIXED_MESSAGE_SIZE_FOR_RANK_SWEEP_BYTES)}")
    print(flush=True)

    results = []
    for algorithm in ALGORITHMS:
        for world_size in RANK_COUNTS:
            print(
                "  starting "
                f"{algorithm:20s} {world_size:>8d} ranks "
                f"at {format_bytes(FIXED_MESSAGE_SIZE_FOR_RANK_SWEEP_BYTES)}",
                flush=True,
            )
            result = launch_worker(
                algorithm=algorithm,
                message_size_bytes=FIXED_MESSAGE_SIZE_FOR_RANK_SWEEP_BYTES,
                world_size=world_size,
            )
            results.append(result)
            print(
                f"  {algorithm:20s} {world_size:>8d} ranks "
                f"-> {result['average_time_ms']:.3f} ms",
                flush=True,
            )

    print(flush=True)
    return {
        "fixed_message_size_bytes": FIXED_MESSAGE_SIZE_FOR_RANK_SWEEP_BYTES,
        "results": results,
    }


# runs the graph generators
def finalize_results(message_sweep_results: dict, rank_scaling_results: dict) -> None:
    ensure_directory(DEFAULT_PLOTS_DIR)
    plot_message_size_sweep(message_sweep_results)
    plot_rank_scaling_sweep(rank_scaling_results)

    print("Generated plots:")
    print(f"  - {MESSAGE_SIZE_PLOT_PATH}", flush=True)
    print(f"  - {RANK_SCALING_PLOT_PATH}", flush=True)


def main() -> None:
    args = build_parser().parse_args()

    # each process will run this same script, but with the --worker flag to trigger worker mode
    if args.worker:
        run_worker(args)
        return

    print("Assignment 5 AllGather benchmark", flush=True)
    print(
        "algorithms: "
        + ", ".join(pretty_algorithm_name(algorithm) for algorithm in ALGORITHMS),
        flush=True,
    )
    print(
        "message sizes: "
        + ", ".join(format_bytes(message_size) for message_size in MESSAGE_SIZES_BYTES),
        flush=True,
    )
    print("rank counts: " + ", ".join(str(rank) for rank in RANK_COUNTS), flush=True)
    print(flush=True)

    message_sweep_results = run_message_size_sweep()
    rank_scaling_results = run_rank_scaling_sweep()
    finalize_results(message_sweep_results, rank_scaling_results)


if __name__ == "__main__":
    main()
