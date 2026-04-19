"""Recursive doubling AllGather implementation for power-of-two world sizes."""

from __future__ import annotations

import torch
import torch.distributed as dist


def allgather_recursive_doubling(
    tensor: torch.Tensor, output_buffer: torch.Tensor, group=None
):
    """Run recursive doubling AllGather on a power-of-two number of ranks."""
    process_group = group if group is not None else dist.group.WORLD
    rank = dist.get_rank(process_group)
    world_size = dist.get_world_size(process_group)

    if world_size & (world_size - 1):
        raise ValueError(
            "Recursive doubling AllGather requires a power-of-two world size."
        )

    local_chunk = tensor.contiguous().view(-1)
    chunks = output_buffer.view(world_size, local_chunk.numel())
    chunks[rank].copy_(local_chunk)

    if world_size == 1:
        return output_buffer

    block_size = 1
    step = 0
    while block_size < world_size:
        group_width = block_size * 2
        group_start = (rank // group_width) * group_width

        if rank < group_start + block_size:
            # first half send to second half and receive from second half
            partner = rank + block_size
            send_start = group_start
            recv_start = group_start + block_size
        else:
            # second half send to first half and receive from first half
            partner = rank - block_size
            send_start = group_start + block_size
            recv_start = group_start

        send_end = send_start + block_size
        recv_end = recv_start + block_size

        send_buffer = chunks[send_start:send_end].reshape(-1)
        recv_buffer = chunks[recv_start:recv_end].view(-1)
        requests = dist.batch_isend_irecv(
            [
                dist.P2POp(
                    dist.isend,
                    send_buffer,
                    partner,
                    process_group,
                    step,
                ),
                dist.P2POp(
                    dist.irecv,
                    recv_buffer,
                    partner,
                    process_group,
                    step,
                ),
            ]
        )
        for request in requests:
            request.wait()

        block_size *= 2
        step += 1

    return output_buffer
