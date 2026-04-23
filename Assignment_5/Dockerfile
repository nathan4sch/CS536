# Assignment-style Docker image for Assignment 5
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    build-essential \
    iproute2 \
    procps \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

COPY . /app/

RUN sed -i 's/\r$//' /app/run_all.sh /app/run_broadcast.sh \
    && chmod +x /app/run_all.sh /app/run_broadcast.sh

ENTRYPOINT ["bash", "/app/run_all.sh"]
