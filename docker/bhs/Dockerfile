# BugHunter Swarm — run bhs-run in a container (local sandbox inside image).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_ROOT_USER_ACTION=ignore \
    BHS_SANDBOX_MODE=local \
    BHS_PROJECT_ROOT=/opt/bhs

WORKDIR /opt/bhs

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY deploy ./deploy

RUN pip install --no-cache-dir .

WORKDIR /workspace

ENTRYPOINT ["bhs-run"]
CMD ["--repo", "/repo"]
