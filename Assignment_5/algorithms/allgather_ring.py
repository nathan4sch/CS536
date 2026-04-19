"""Ring AllGather implementation using point-to-point PyTorch gloo operations."""

from __future__ import annotations

import torch
import torch.distributed as dist


def allgather_ring(tensor: torch.Tensor, output_buffer: torch.Tensor, group=None):
    """Run a standard ring AllGather over the provided process group."""
    process_group = group if group is not None else dist.group.WORLD
    rank = dist.get_rank(process_group)
    world_size = dist.get_world_size(process_group)

    local_chunk = tensor.contiguous().view(-1)
    chunks = output_buffer.view(world_size, local_chunk.numel())
    chunks[rank].copy_(local_chunk)

    if world_size == 1:
        return output_buffer

    send_peer = (rank + 1) % world_size
    recv_peer = (rank - 1) % world_size
    current_chunk_index = rank
    recv_chunk = torch.empty_like(local_chunk)

    for step in range(world_size - 1):
        recv_origin = (rank - step - 1) % world_size

        requests = dist.batch_isend_irecv(
            [
                dist.P2POp(
                    dist.isend,
                    chunks[current_chunk_index].view(-1),
                    send_peer,
                    process_group,
                    step,
                ),
                dist.P2POp(
                    dist.irecv,
                    recv_chunk,
                    recv_peer,
                    process_group,
                    step,
                ),
            ]
        )

        for request in requests:
            request.wait()

        chunks[recv_origin].copy_(recv_chunk)
        current_chunk_index = recv_origin

    return output_buffer
