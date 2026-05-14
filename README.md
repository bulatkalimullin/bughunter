# BugHunter Swarm (BHS)

Локальный каркас **иерархического multi-agent DAG**: SQLite state + audit, LangGraph граф (`CodeAnalyzer` → `TestGenerator` → `RuntimeExecutor` → условные `MemoryProfiler` / `ABTester` → `BugLogger`), Docker/Podman sandbox (или `BHS_SANDBOX_MODE=local` для CI), артефакты (локально или MinIO), OpenTelemetry OTLP HTTP, Prometheus metrics.

## Установка

```bash
cd "/home/bulatkalimullin/Рабочий стол/repositories/Lessons/15.05"
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Запуск

```bash
# Изолированный compileall в контейнере (нужен Docker и образ BHS_SANDBOX_IMAGE)
bhs-run --repo /path/to/repo

# Без Docker (хостовый subprocess, для CI/разработки)
BHS_SANDBOX_MODE=local bhs-run --repo .

# Метрики Prometheus
bhs-run --repo . --metrics-port 9108
```

Переменные: см. [`src/bhs/config.py`](src/bhs/config.py) (`BHS_*`), `OTEL_EXPORTER_OTLP_ENDPOINT`, `BHS_SECCOMP_PROFILE`, `BHS_SANDBOX_IMAGE`.

## Сборка sandbox-образа

```bash
docker build -t bughunter-sandbox:local -f docker/sandbox/Dockerfile .
```

## Документация

- [docs/BHS_IMPLEMENTATION.md](docs/BHS_IMPLEMENTATION.md) — чеклист и DAG.
- [docs/prompts/hypervisor_system_v1.txt](docs/prompts/hypervisor_system_v1.txt) — системный промпт HyperVisor.
- [deploy/docker-compose.observability.yml](deploy/docker-compose.observability.yml) — MinIO, Redis, Prometheus, Grafana, Loki (черновой стек).

## Участие и политики

- [CONTRIBUTING.md](CONTRIBUTING.md) — установка, `ruff`, `pytest`, локальный режим `BHS_SANDBOX_MODE`.
- [SECURITY.md](SECURITY.md) — ответственное раскрытие уязвимостей.

## Лицензия

Проект распространяется под лицензией MIT; см. [LICENSE](LICENSE).

Перед первым push на GitHub замените в [pyproject.toml](pyproject.toml) в секции `[project.urls]` placeholder `OWNER` на имя организации или пользователя.
