FROM golang:1.22 AS go-toolchain
FROM maven:3.9-eclipse-temurin-11 AS maven-toolchain
FROM secevo-java-js-baseplus-validator:current
COPY --from=go-toolchain /usr/local/go /usr/local/go
COPY --from=maven-toolchain /usr/share/maven /usr/share/maven
USER root
RUN apt-get update && apt-get install -y --no-install-recommends python3-pip python3-venv gcc g++ cmake libarchive-dev libxml2-dev libsqlite3-dev libjwt-dev libssl-dev pkg-config && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/audit && /opt/audit/bin/python -m pip install --no-cache-dir pytest pytest-xdist pytest-timeout wrapt_timeout_decorator fire natsort p_tqdm numpy flask requests lxml pyyaml PyJWT argon2-cffi pycryptodome cryptography python-jose defusedxml paramiko boto3 func-timeout django pytest-httpserver pytest-mock bandit semgrep
ENV PATH="/opt/audit/bin:${PATH}"
RUN /opt/audit/bin/python -m pip install --no-cache-dir Flask-SQLAlchemy==3.0.5 canvasapi==3.3.0 psycopg2-binary pymysql && /opt/audit/bin/python -m venv --system-site-packages /opt/sallm && /opt/sallm/bin/python -m pip install --no-cache-dir Flask==2.3.3 Flask-SQLAlchemy==3.0.5
RUN npm install -g escape-html node-rsa argon2@0.41.1 escape-string-regexp@4 lodash js-yaml jsonwebtoken jsdom@22 xpath sqlite3
ENV NODE_PATH="/usr/local/lib/node_modules:/usr/lib/node_modules"
ENV PATH="/usr/share/maven/bin:/usr/local/go/bin:${PATH}"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /work
CMD ["tail", "-f", "/dev/null"]
