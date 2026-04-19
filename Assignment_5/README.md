# Assignment 5

This folder contains the AllGather portion of the assignment using the PyTorch `gloo` backend.

Implemented algorithms:

- Ring
- Recursive doubling
- Swing

The benchmark script is a one-shot runner. It:

- validates correctness
- runs the message-size sweep
- runs the rank-scaling sweep
- generates the two AllGather plots

## Docker

From inside `Assignment_5`:

```bash
docker build -t hw5_image .
docker run --rm -v "$(pwd)/plots:/app/plots" hw5_image
```

Plots are written to:

- `plots/allgather_vs_message_size.png`
- `plots/allgather_vs_ranks.png`
