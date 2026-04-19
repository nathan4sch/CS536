"""Distributed helpers for local PyTorch gloo benchmarks."""

from __future__ import annotations


def setup_process_group(backend: str = "gloo") -> None:
    """Initialize the default process group from torchrun environment variables."""
    import torch.distributed as dist

    if dist.is_initialized():
        return

    dist.init_process_group(backend=backend, init_method="env://")


def cleanup_process_group() -> None:
    """Destroy the default process group when it has been initialized."""
    import torch.distributed as dist

    if dist.is_available() and dist.is_initialized():
        dist.destroy_process_group()


def get_rank_metadata() -> dict[str, int]:
    """Return rank metadata for the current worker process."""
    import torch.distributed as dist

    if not dist.is_available() or not dist.is_initialized():
        raise RuntimeError("Process group must be initialized before reading rank info.")

    return {
        "rank": dist.get_rank(),
        "world_size": dist.get_world_size(),
    }
