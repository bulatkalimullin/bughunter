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

# Тот же путь из .env (BHS_REPO_PATH), без флага --repo
export BHS_REPO_PATH=/path/to/repo
BHS_SANDBOX_MODE=local bhs-run

# Без Docker (хостовый subprocess, для CI/разработки)
BHS_SANDBOX_MODE=local bhs-run --repo .

# Метрики Prometheus
bhs-run --repo . --metrics-port 9108
```

Переменные: см. [`src/bhs/config.py`](src/bhs/config.py) (`BHS_*`), `BHS_REPO_PATH`, `BHS_MAX_ITERATIONS`, `BHS_STOP_BUG_COUNT`, `BHS_SANDBOX_CPU_BUDGET_SECONDS`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `BHS_SECCOMP_PROFILE`, `BHS_SANDBOX_IMAGE`. Пример — [.env.example](.env.example).

### Минимальное окружение

Только Python и зависимости; sandbox на хосте:

```bash
BHS_SANDBOX_MODE=local bhs-run --repo .
```

Подробнее: [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md).

### Ollama (опционально)

При `BHS_OLLAMA_ENABLED=true` перед запуском графа `bhs-run` сам поднимает Ollama через [deploy/docker-compose.llm.yml](deploy/docker-compose.llm.yml) (если API недоступен) и при необходимости тянет модель. Нужны Docker или Podman и либо запуск из корня репозитория, либо `BHS_PROJECT_ROOT`. Отключить автоматику: `BHS_SKIP_AUTO_OLLAMA=true`.

```bash
export BHS_OLLAMA_ENABLED=true
export BHS_OLLAMA_MODEL=gemma3:1b
BHS_SANDBOX_MODE=local bhs-run --repo .
```

Опционально для «полного» локального стека: `BHS_AUTO_SANDBOX_IMAGE=true` (без `BHS_SANDBOX_MODE=local` — сборка образа sandbox при отсутствии), `BHS_AUTO_OBSERVABILITY=true` (MinIO, Redis, Prometheus и т.д.). Подробнее — [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md).

## Сборка sandbox-образа

Вручную:

```bash
docker build -t bughunter-sandbox:local -f docker/sandbox/Dockerfile .
```

## Документация

- [docs/BHS_IMPLEMENTATION.md](docs/BHS_IMPLEMENTATION.md) — чеклист и DAG.
- [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md) — минимальное и полное окружение, Ollama.
- [docs/prompts/hypervisor_system_v1.txt](docs/prompts/hypervisor_system_v1.txt) — системный промпт HyperVisor.
- [deploy/docker-compose.observability.yml](deploy/docker-compose.observability.yml) — MinIO, Redis, Prometheus, Grafana, Loki (черновой стек).
- [deploy/docker-compose.llm.yml](deploy/docker-compose.llm.yml) — Ollama для LLM-тестов.
- [docker-compose.yml](docker-compose.yml) — запуск `bhs-run` в контейнере (см. ниже).

## Docker Compose

Корневой [`docker-compose.yml`](docker-compose.yml) через **`include`** подмешивает [deploy/docker-compose.llm.yml](deploy/docker-compose.llm.yml) и [deploy/docker-compose.observability.yml](deploy/docker-compose.observability.yml): в одном проекте сервисы **bhs**, **ollama**, **minio**, **redis**, **prometheus**, **grafana**, **loki**.

```bash
cd "/path/to/bughunter-swarm"
docker compose build
# поднять весь стек
docker compose up -d
# только прогон анализа (остальные сервисы не обязательны)
docker compose run --rm bhs
# только bhs как долгоживущий контейнер
docker compose up -d bhs
```

Состояние SQLite и артефакты по умолчанию пишутся в каталог **`.bhs.docker/`** у корня compose (можно переопределить переменной `BHS_DOCKER_STATE`).

Сервис по умолчанию настроен на **до 250 итераций** feedback-loop или **ранний выход**, если после dedupe в отчёте **не меньше 2** записей (`BHS_STOP_BUG_COUNT`), без Ollama. Переопределите `BHS_MAX_ITERATIONS` / `BHS_STOP_BUG_COUNT` в `.env` или через `docker compose run -e`.

Если включили **`BHS_OLLAMA_ENABLED=true`** в том же compose-проекте, задайте **`BHS_OLLAMA_BASE_URL=http://ollama:11434`** (имя сервиса из include). Для Ollama **только на хосте** используйте `http://host.docker.internal:11434` и при необходимости `extra_hosts: ["host.docker.internal:host-gateway"]` у сервиса `bhs`.

## Участие и политики

- [CONTRIBUTING.md](CONTRIBUTING.md) — установка, `ruff`, `pytest`, локальный режим `BHS_SANDBOX_MODE`.
- [SECURITY.md](SECURITY.md) — ответственное раскрытие уязвимостей.

## Лицензия

Проект распространяется под лицензией MIT; см. [LICENSE](LICENSE).

Перед первым push на GitHub замените в [pyproject.toml](pyproject.toml) в секции `[project.urls]` placeholder `OWNER` на имя организации или пользователя.
