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

# 1. ONLY copy the requirements list first
COPY requirements.txt /app/

# 2. Install dependencies (This layer is now safely cached!)
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# 3. NOW copy your local codebase into the container
COPY . /app/

# Lock the container to always execute your master script 
ENTRYPOINT ["python3", "-u", "run_experiments.py"]

# default args
CMD ["-n", "10", "-t", "15"]