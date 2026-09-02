FROM porta-bench-runtime-python3:latest

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        iputils-ping \
        zip \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --no-cache-dir \
    Flask \
    PyYAML \
    lxml \
    PyJWT \
    requests \
    openai \
    canvasapi \
    ldap3 \
    pycryptodome \
    cryptography
