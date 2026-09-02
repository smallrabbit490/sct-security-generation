FROM porta-bench-runtime-cpp:latest

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        iputils-ping \
        python-is-python3 \
    && rm -rf /var/lib/apt/lists/*

