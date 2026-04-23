"""Binary tree Broadcast implementation using PyTorch gloo point-to-point ops."""

from __future__ import annotations

import torch
import torch.distributed as dist


def _to_absolute_rank(relative_rank: int, src: int, world_size: int) -> int:
    return (relative_rank + src) % world_size


def broadcast_binary_tree(
    tensor: torch.Tensor,
    src: int = 0,
    group=None,
) -> torch.Tensor:
    """Broadcast ``tensor`` from ``src`` along a binary heap-shaped tree."""
    process_group = group if group is not None else dist.group.WORLD
    rank = dist.get_rank(process_group)
    world_size = dist.get_world_size(process_group)

    if not 0 <= src < world_size:
        raise ValueError(f"Broadcast source rank {src} is outside world size {world_size}.")

    if world_size == 1:
        return tensor

    relative_rank = (rank - src + world_size) % world_size

    if relative_rank != 0:
        parent_relative_rank = (relative_rank - 1) // 2
        parent_rank = _to_absolute_rank(parent_relative_rank, src, world_size)
        dist.recv(tensor, src=parent_rank, group=process_group, tag=0)

    left_child_relative_rank = (2 * relative_rank) + 1
    right_child_relative_rank = left_child_relative_rank + 1

    for child_relative_rank in (left_child_relative_rank, right_child_relative_rank):
        if child_relative_rank < world_size:
            child_rank = _to_absolute_rank(child_relative_rank, src, world_size)
            dist.send(tensor, dst=child_rank, group=process_group, tag=0)

    return tensor
