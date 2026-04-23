"""Shared constants and helpers for Assignment 5 benchmarks."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_PLOTS_DIR = BASE_DIR / "plots"
GLOO_BACKEND = "gloo"


def ensure_directory(path: Path) -> None:
    """Create a directory if it does not already exist."""
    path.mkdir(parents=True, exist_ok=True)


def is_power_of_two(value: int) -> bool:
    """Return True when the input is a positive power of two."""
    return value > 0 and (value & (value - 1)) == 0


def format_bytes(num_bytes: int) -> str:
    """Format a byte count for axis labels and logs."""
    units = ["B", "KB", "MB", "GB"]
    value = float(num_bytes)
    for unit in units:
        if value < 1024.0 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            if value.is_integer():
                return f"{int(value)} {unit}"
            return f"{value:.2f} {unit}"
        value /= 1024.0
    return f"{num_bytes} B"


def build_input_tensor(rank: int, message_size_bytes: int):
    """Create deterministic per-rank input data for correctness checks."""
    import torch

    positions = torch.arange(message_size_bytes, dtype=torch.int32)
    return ((positions + (rank * 17)) % 251).to(torch.uint8)


def validate_allgather_output(output_buffer, message_size_bytes: int) -> bool:
    """Verify that each gathered chunk matches the expected source-rank payload."""
    import torch

    world_size = int(output_buffer.shape[0])
    expected_shape = (world_size, message_size_bytes)
    if tuple(output_buffer.shape) != expected_shape:
        return False

    for source_rank in range(world_size):
        expected = build_input_tensor(source_rank, message_size_bytes)
        if not torch.equal(output_buffer[source_rank], expected):
            return False
    return True


def build_broadcast_tensor(rank: int, source_rank: int, message_size_bytes: int):
    """Create the per-rank input buffer used for Broadcast correctness checks."""
    import torch

    if rank == source_rank:
        return build_input_tensor(source_rank, message_size_bytes)
    return torch.empty(message_size_bytes, dtype=torch.uint8)


def validate_broadcast_output(tensor, source_rank: int, message_size_bytes: int) -> bool:
    """Verify that a Broadcast result matches the source-rank payload."""
    import torch

    expected = build_input_tensor(source_rank, message_size_bytes)
    return tuple(tensor.shape) == (message_size_bytes,) and torch.equal(tensor, expected)


def plot_message_size_results(
    results: list[dict],
    algorithms: list[str],
    message_sizes_bytes: list[int],
    fixed_rank: int,
    collective_name: str,
    output_path: Path,
) -> None:
    """Plot completion time against message size for a collective benchmark."""
    import matplotlib.pyplot as plt

    grouped = defaultdict(list)
    for result in results:
        grouped[result["algorithm"]].append(result)

    figure, axis = plt.subplots(figsize=(10, 6))
    for algorithm in algorithms:
        points = sorted(grouped[algorithm], key=lambda item: item["message_size_bytes"])
        axis.plot(
            [point["message_size_bytes"] for point in points],
            [point["average_time_ms"] for point in points],
            marker="o",
            linewidth=2,
            label=pretty_algorithm_name(algorithm),
        )

    axis.set_xscale("log", base=2)
    axis.set_xlabel("Message Size")
    axis.set_ylabel("Completion Time (ms)")
    axis.set_title(
        f"{collective_name} Completion Time vs Message Size ({fixed_rank} ranks)"
    )
    axis.grid(True, which="both", linestyle="--", linewidth=0.5, alpha=0.7)
    axis.legend()
    axis.set_xticks(message_sizes_bytes)
    axis.set_xticklabels(
        [format_bytes(value) for value in message_sizes_bytes],
        rotation=30,
        ha="right",
    )

    figure.tight_layout()
    figure.savefig(output_path, dpi=200)
    plt.close(figure)


def plot_rank_scaling_results(
    results: list[dict],
    algorithms: list[str],
    rank_counts: list[int],
    fixed_message_size_bytes: int,
    collective_name: str,
    output_path: Path,
) -> None:
    """Plot completion time against rank count for a collective benchmark."""
    import matplotlib.pyplot as plt

    grouped = defaultdict(list)
    for result in results:
        grouped[result["algorithm"]].append(result)

    figure, axis = plt.subplots(figsize=(10, 6))
    for algorithm in algorithms:
        points = sorted(grouped[algorithm], key=lambda item: item["world_size"])
        axis.plot(
            [point["world_size"] for point in points],
            [point["average_time_ms"] for point in points],
            marker="o",
            linewidth=2,
            label=pretty_algorithm_name(algorithm),
        )

    axis.set_xlabel("Number of Ranks")
    axis.set_ylabel("Completion Time (ms)")
    axis.set_title(
        f"{collective_name} Completion Time vs Number of Ranks "
        f"({format_bytes(fixed_message_size_bytes)})"
    )
    axis.grid(True, linestyle="--", linewidth=0.5, alpha=0.7)
    axis.legend()
    axis.set_xticks(rank_counts)

    figure.tight_layout()
    figure.savefig(output_path, dpi=200)
    plt.close(figure)


def pretty_algorithm_name(name: str) -> str:
    """Convert internal identifiers into plot-friendly labels."""
    return {
        "ring": "Ring",
        "recursive_doubling": "Recursive Doubling",
        "swing": "Swing",
        "binary_tree": "Binary Tree",
        "binomial_tree": "Binomial Tree",
    }.get(name, name.replace("_", " ").title())
