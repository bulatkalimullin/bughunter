FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    strace \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 65532 -s /usr/sbin/nologin bhsuser

WORKDIR /workspace
USER bhsuser

# Runtime installs tests deps on demand in CI images; base image keeps toolchain minimal.
CMD ["python", "-V"]
