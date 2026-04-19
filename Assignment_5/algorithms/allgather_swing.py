"""Swing AllGather implementation following the lecture-slide schedule."""

from __future__ import annotations

from functools import lru_cache

import torch
import torch.distributed as dist


def _rho(step: int) -> int:
    """Return rho(step) = sum_{i=0}^{step} (-2)^i from the lecture slides."""
    return sum((-2) ** i for i in range(step + 1))


def _swing_peer(rank: int, step: int, world_size: int) -> int:
    """Peer function pi(r, s) from the lecture slides."""
    offset = _rho(step)
    if rank % 2 == 0:
        return (rank + offset) % world_size
    return (rank - offset) % world_size


def _pack_blocks(chunks: torch.Tensor, block_indices: tuple[int, ...]) -> torch.Tensor:
    """Collect the selected blocks into one contiguous send buffer."""
    packed = torch.stack([chunks[index] for index in block_indices], dim=0)
    return packed.contiguous().view(-1)


def allgather_swing(tensor: torch.Tensor, output_buffer: torch.Tensor, group=None):
    """Run Swing AllGather using the reverse-order peer schedule from lecture.

    The slide deck defines Swing AllGather by reversing the reduce-scatter peer
    order. At step s, a rank communicates with pi(r, log2(n) - 1 - s) and sends
    all blocks gathered so far.
    """

    process_group = group if group is not None else dist.group.WORLD
    rank = dist.get_rank(process_group)
    world_size = dist.get_world_size(process_group)

    if world_size & (world_size - 1):
        raise ValueError("Swing AllGather requires a power-of-two world size.")

    local_chunk = tensor.contiguous().view(-1)
    chunks = output_buffer.view(world_size, local_chunk.numel())
    chunks[rank].copy_(local_chunk)

    if world_size == 1:
        return output_buffer

    total_steps = world_size.bit_length() - 1

    @lru_cache(maxsize=None)
    def gathered_blocks(node_rank: int, completed_steps: int) -> tuple[int, ...]:
        """Recursively describe which blocks a rank owns after some steps.

        This mirrors the recursive block-selection idea from the lecture slides:
        after each Swing step, a rank keeps the blocks it already had and adds
        the blocks owned by its current peer.
        """

        if completed_steps == 0:
            return (node_rank,)

        previous_blocks = gathered_blocks(node_rank, completed_steps - 1)
        peer = _swing_peer(node_rank, total_steps - completed_steps, world_size)
        peer_blocks = gathered_blocks(peer, completed_steps - 1)
        return previous_blocks + peer_blocks

    for step in range(total_steps):
        peer = _swing_peer(rank, total_steps - 1 - step, world_size)

        send_indices = gathered_blocks(rank, step)
        recv_indices = gathered_blocks(peer, step)

        send_buffer = _pack_blocks(chunks, send_indices)
        recv_buffer = torch.empty(
            len(recv_indices) * local_chunk.numel(),
            dtype=local_chunk.dtype,
            device=local_chunk.device,
        )

        requests = dist.batch_isend_irecv(
            [
                dist.P2POp(
                    dist.isend,
                    send_buffer,
                    peer,
                    process_group,
                    step,
                ),
                dist.P2POp(
                    dist.irecv,
                    recv_buffer,
                    peer,
                    process_group,
                    step,
                ),
            ]
        )
        for request in requests:
            request.wait()

        received_blocks = recv_buffer.view(len(recv_indices), local_chunk.numel())
        for block_index, block_tensor in zip(recv_indices, received_blocks):
            chunks[block_index].copy_(block_tensor)

    return output_buffer
