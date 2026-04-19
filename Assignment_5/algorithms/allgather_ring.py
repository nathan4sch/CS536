"""Ring AllGather implementation using point-to-point PyTorch gloo operations."""

from __future__ import annotations

import torch
import torch.distributed as dist


def allgather_ring(tensor: torch.Tensor, output_buffer: torch.Tensor, group=None):
    """Run a standard ring AllGather over the provided process group."""
    # get current rank and world size
    process_group = group if group is not None else dist.group.WORLD
    rank = dist.get_rank(process_group)
    world_size = dist.get_world_size(process_group)

    # copy local chunk into the correct position in the output buffer
    local_chunk = tensor.contiguous().view(-1)
    chunks = output_buffer.view(world_size, local_chunk.numel())
    chunks[rank].copy_(local_chunk)

    if world_size == 1:
        return output_buffer

    # ring 0 sends to 1, 1 sends to 2, ..., N-1 sends to 0
    send_peer = (rank + 1) % world_size
    recv_peer = (rank - 1) % world_size
    current_chunk = local_chunk.clone()

    for step in range(world_size - 1): # n - 1 steps
        recv_chunk = torch.empty_like(local_chunk) # buffer to receive the incoming chunk
        recv_origin = (rank - step - 1) % world_size # rank of incoming info

        # send to next rank and receive from previous rank at the same time
        requests = dist.batch_isend_irecv(
            [
                dist.P2POp(
                    dist.isend,
                    current_chunk,
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
            request.wait() # wait for both send and receive to complete

        # Store the received chunk in the correct position
        chunks[recv_origin].copy_(recv_chunk)
        current_chunk = recv_chunk # forward new chunk along the ring

    return output_buffer
