# Assignment 5

This folder contains the AllGather and Broadcast portions of the assignment using the PyTorch `gloo` backend.

Implemented AllGather algorithms:

- Ring
- Recursive doubling
- Swing

Implemented Broadcast algorithms:

- Binary tree
- Binomial tree

The benchmark scripts are one-shot runners. They:

- validate correctness
- run the message-size sweep
- run the rank-scaling sweep
- generate the plots

## Docker

From inside `Assignment_5`:

```bash
docker build -t hw5_image .
docker run --rm -v "$(pwd)/plots:/app/plots" hw5_image
```

The Docker command runs the AllGather algorithms by default. To run Broadcast:

```bash
docker run --rm -v "$(pwd)/plots:/app/plots" hw5_image broadcast
```

To run both benchmark groups:

```bash
docker run --rm -v "$(pwd)/plots:/app/plots" hw5_image all
```

Plots are written to:

- `plots/allgather_vs_message_size.png`
- `plots/allgather_vs_ranks.png`
- `plots/broadcast_vs_message_size.png`
- `plots/broadcast_vs_ranks.png`
