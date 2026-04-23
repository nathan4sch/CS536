"""Binomial tree Broadcast implementation using PyTorch gloo point-to-point ops."""

from __future__ import annotations

import torch
import torch.distributed as dist


def _to_absolute_rank(relative_rank: int, src: int, world_size: int) -> int:
    return (relative_rank + src) % world_size


def broadcast_binomial_tree(
    tensor: torch.Tensor,
    src: int = 0,
    group=None,
) -> torch.Tensor:
    """Broadcast ``tensor`` from ``src`` using a binomial tree schedule."""
    process_group = group if group is not None else dist.group.WORLD
    rank = dist.get_rank(process_group)
    world_size = dist.get_world_size(process_group)

    if not 0 <= src < world_size:
        raise ValueError(f"Broadcast source rank {src} is outside world size {world_size}.")

    if world_size == 1:
        return tensor

    relative_rank = (rank - src + world_size) % world_size
    mask = 1
    while mask < world_size:
        if relative_rank < mask:
            destination_relative_rank = relative_rank + mask
            if destination_relative_rank < world_size:
                destination_rank = _to_absolute_rank(
                    destination_relative_rank,
                    src,
                    world_size,
                )
                dist.send(tensor, dst=destination_rank, group=process_group, tag=mask)
        elif relative_rank < (2 * mask):
            source_relative_rank = relative_rank - mask
            source_rank = _to_absolute_rank(source_relative_rank, src, world_size)
            dist.recv(tensor, src=source_rank, group=process_group, tag=mask)

        mask *= 2

    return tensor
