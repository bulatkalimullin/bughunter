# BugHunter Swarm (BHS)

Локальный каркас **иерархического multi-agent DAG**: SQLite state + audit, LangGraph (`CodeAnalyzer` → `TestGenerator` → `RuntimeExecutor` → условные `MemoryProfiler` / `ABTester` → `BugLogger` → feedback-loop), Docker/Podman sandbox (или `BHS_SANDBOX_MODE=local` для CI), артефакты (локально или MinIO), OpenTelemetry OTLP HTTP, Prometheus metrics.

**Содержание:** [Установка](#установка) · [Запуск](#запуск) · [Bootstrap](#автозапуск-bootstrap) · [Мониторинг](#мониторинг-прогона) · [Docker Compose](#docker-compose) · [Документация](#документация) · [Участие](#участие-и-политики)

## Установка

```bash
cd /path/to/bughunter-swarm
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Альтернатива: `uv sync --extra dev` (см. [CONTRIBUTING.md](CONTRIBUTING.md)).

## Запуск

```bash
# Анализ репозитория (Docker sandbox — нужен образ BHS_SANDBOX_IMAGE)
bhs-run --repo /path/to/repo

# Путь к цели из .env (CLI --repo важнее BHS_REPO_PATH)
export BHS_REPO_PATH=/path/to/repo
BHS_SANDBOX_MODE=local bhs-run

# Локальная песочница (subprocess), удобно для CI
BHS_SANDBOX_MODE=local bhs-run --repo .

# Лимит итераций feedback-loop и ранний выход по числу dedupe-багов
export BHS_MAX_ITERATIONS=250
export BHS_STOP_BUG_COUNT=2   # 0 = отключить ранний выход по багам
BHS_SANDBOX_MODE=local bhs-run --repo .

# Метрики Prometheus на порту
bhs-run --repo . --metrics-port 9108
```

Полный список переменных: [`src/bhs/config.py`](src/bhs/config.py) (`BHS_*`), шаблон [.env.example](.env.example), гайд [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md).

### Минимальное окружение

Только Python и зависимости; sandbox на хосте:

```bash
BHS_SANDBOX_MODE=local bhs-run --repo .
```

## Автозапуск (bootstrap)

Перед графом [`run_dev_bootstrap`](src/bhs/dev_bootstrap.py) (после загрузки `Settings` в [`cli.py`](src/bhs/cli.py)):

| Условие | Действие |
|---------|----------|
| `BHS_AUTO_OBSERVABILITY=true` | `docker compose` / `podman compose` для observability-стека из `deploy/` |
| `BHS_OLLAMA_ENABLED=true` и не `BHS_SKIP_AUTO_OLLAMA` | поднять Ollama compose при недоступном API, при необходимости `pull` модели |
| `BHS_AUTO_SANDBOX_IMAGE=true` и не `local` sandbox | собрать образ `BHS_SANDBOX_IMAGE`, если его нет |

Корень репозитория с `deploy/`: см. `BHS_PROJECT_ROOT` и [`src/bhs/paths.py`](src/bhs/paths.py). **Если поднят корневой [`docker-compose.yml`](docker-compose.yml) с `include` observability, держите `BHS_AUTO_OBSERVABILITY=false`**, иначе возможен конфликт портов.

## Мониторинг прогона

- **Итог в stdout:** JSON `last_hypervisor` — `status`, `metrics` (`tests_run`, `cpu_sec`), `artifacts`, `bugs_found`.
- **Отчёт:** `BugHunter_Report.md` в каталоге отчётов артефактов.
- **SQLite:** `BHS_SQLITE_PATH` (по умолчанию `.bhs/state.sqlite`), таблицы `runs`, `audit_log`.
- **Prometheus:** `bhs-run --metrics-port <port>` → `GET /metrics`.
- **OTEL:** `OTEL_EXPORTER_OTLP_ENDPOINT` / `BHS_OTEL_EXPORTER_OTLP_ENDPOINT`.

### Ollama (опционально)

При `BHS_OLLAMA_ENABLED=true` bootstrap может поднять [deploy/docker-compose.llm.yml](deploy/docker-compose.llm.yml). В одном корневом compose-проекте задайте `BHS_OLLAMA_BASE_URL=http://ollama:11434`. Отключить только автоподъём: `BHS_SKIP_AUTO_OLLAMA=true`.

```bash
export BHS_OLLAMA_ENABLED=true
export BHS_OLLAMA_MODEL=gemma3:1b
BHS_SANDBOX_MODE=local bhs-run --repo .
```

Дополнительно: `BHS_AUTO_SANDBOX_IMAGE` (без `local` — сборка sandbox при отсутствии образа). Подробнее — [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md).

## Сборка sandbox-образа

```bash
docker build -t bughunter-sandbox:local -f docker/sandbox/Dockerfile .
```

## Документация

- [docs/BHS_IMPLEMENTATION.md](docs/BHS_IMPLEMENTATION.md) — DAG, чеклист, backlog.
- [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md) — переменные, compose, итерации, bootstrap.
- [docs/prompts/hypervisor_system_v1.txt](docs/prompts/hypervisor_system_v1.txt) — системный промпт HyperVisor.
- [deploy/docker-compose.observability.yml](deploy/docker-compose.observability.yml) — MinIO, Redis, Prometheus, Grafana, Loki.
- [deploy/docker-compose.llm.yml](deploy/docker-compose.llm.yml) — Ollama (также подключается из корневого compose).
- [docker-compose.yml](docker-compose.yml) — образ приложения `bhs` + `include` стека выше.

## Docker Compose

Корневой [`docker-compose.yml`](docker-compose.yml) через **`include`** объединяет **bhs** с [deploy/docker-compose.llm.yml](deploy/docker-compose.llm.yml) и [deploy/docker-compose.observability.yml](deploy/docker-compose.observability.yml): сервисы **bhs**, **ollama**, **minio**, **redis**, **prometheus**, **grafana**, **loki** (`docker compose config --services`).

```bash
cd /path/to/bughunter-swarm
docker compose build
docker compose up -d          # весь стек
docker compose run --rm bhs   # одноразовый прогон анализа
docker compose up -d bhs      # только контейнер bhs
```

- **`TARGET_REPO`** — хост-путь к анализируемому репозиторию (bind → `/repo` в контейнере).
- **`BHS_DOCKER_STATE`** — каталог на хосте для `.bhs` внутри контейнера (по умолчанию `./.bhs.docker`).

В `environment` сервиса `bhs` заданы примеры **`BHS_MAX_ITERATIONS`**, **`BHS_STOP_BUG_COUNT`**, **`BHS_OLLAMA_ENABLED`** — переопределяйте в `.env`.

## Участие и политики

- [CONTRIBUTING.md](CONTRIBUTING.md) — установка, `ruff`, `pytest`, Docker.
- [SECURITY.md](SECURITY.md) — ответственное раскрытие уязвимостей.

## Лицензия

Проект распространяется под лицензией MIT; см. [LICENSE](LICENSE).

Перед первым push на GitHub замените в [pyproject.toml](pyproject.toml) в секции `[project.urls]` placeholder `OWNER` на имя организации или пользователя.
