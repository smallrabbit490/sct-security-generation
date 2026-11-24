FROM golang:1.23.3 AS go
FROM cle-external-bank:20261117
COPY --from=go /usr/local/go /opt/go123
ENV PATH="/opt/go123/bin:${PATH}"
