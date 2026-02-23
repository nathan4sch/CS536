# Assignment strict requirement
FROM ubuntu:24.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install networking, debugging, and Python tools
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    tcpdump \
    iperf3 \
    iproute2 \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy the local codebase into the container
COPY . /app

# Install ML and plotting dependencies globally in the container
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# The full pipeline automation script
ENTRYPOINT ["python3", "run_experiments.py"]