"""Shared constants and helpers for Assignment 5 benchmarks."""

from __future__ import annotations

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


def pretty_algorithm_name(name: str) -> str:
    """Convert internal identifiers into plot-friendly labels."""
    return {
        "ring": "Ring",
        "recursive_doubling": "Recursive Doubling",
        "swing": "Swing",
    }.get(name, name.replace("_", " ").title())
