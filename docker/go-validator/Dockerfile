FROM golang:1.22

# Keep compiler and module caches on the host when this image is used by the
# validator; the runner supplies the corresponding mounts and environment.
ENV GOTMPDIR=/work/.tmp \
    GOCACHE=/work/.cache/go-build \
    GOMODCACHE=/work/.cache/go-mod
WORKDIR /work
