# Окружение BugHunter Swarm

## Минимальное (без внешних сервисов)

| Компонент | Нужно |
|-----------|--------|
| Python | 3.11+ |
| Зависимости | `pip install -e ".[dev]"` или `uv sync --extra dev` |
| Sandbox | `BHS_SANDBOX_MODE=local` (subprocess на хосте) |
| Цель анализа | `BHS_REPO_PATH` или `bhs-run --repo` (флаг важнее env) |

```bash
BHS_SANDBOX_MODE=local bhs-run --repo .
```

```bash
export BHS_REPO_PATH=/path/to/project-under-test
BHS_SANDBOX_MODE=local bhs-run
```

## Итерации feedback-loop и квоты

| Переменная | По умолчанию | Описание |
|------------|----------------|----------|
| `BHS_MAX_ITERATIONS` | `1` | Сколько раз может крутиться цикл `bug_logger` → `feedback_tick` → `test_generator` → … (верхняя граница в конфиге до `5000`) |
| `BHS_STOP_BUG_COUNT` | `0` | Если `>0`, после dedupe в `bug_logger` при `len(bugs) >=` порога — `finalize`. Статика может сразу дать много находок — цикл завершится после первого `bug_logger`, если dedupe-список уже ≥ порога. |
| `BHS_SANDBOX_CPU_BUDGET_SECONDS` | (авто) | Лимит `cpu_seconds` в `sandbox_limits` для [`check_quotas`](../src/bhs/hypervisor/router.py). Если не задан: `max(120, 3 * BHS_MAX_ITERATIONS)` секунд. |

## Автозапуск перед `bhs-run` (bootstrap)

Модуль [`src/bhs/dev_bootstrap.py`](../src/bhs/dev_bootstrap.py), вызывается из [`cli.py`](../src/bhs/cli.py) после `Settings()`.

| Переменная | По умолчанию | Описание |
|------------|----------------|----------|
| `BHS_AUTO_OBSERVABILITY` | `false` | `compose up -d` для [docker-compose.observability.yml](../deploy/docker-compose.observability.yml) |
| `BHS_AUTO_SANDBOX_IMAGE` | `false` | Если не `BHS_SANDBOX_MODE=local`, собрать образ `BHS_SANDBOX_IMAGE`, если отсутствует |
| `BHS_SKIP_AUTO_OLLAMA` | `false` | Не поднимать LLM compose и не делать `pull` при `BHS_OLLAMA_ENABLED` |
| `BHS_PROJECT_ROOT` | — | Корень checkout с каталогом `deploy/` (см. [`paths.py`](../src/bhs/paths.py)) |

При **`BHS_CONTAINER_RUNTIME=podman`** для compose вызывается `podman compose`.

**Корневой [`docker-compose.yml`](../docker-compose.yml)** уже поднимает observability через `include`. В этом случае задайте **`BHS_AUTO_OBSERVABILITY=false`**, чтобы bootstrap не запускал второй экземпляр на те же порты.

## Ollama (LLM для TestGenerator)

| Переменная | По умолчанию | Описание |
|------------|----------------|----------|
| `BHS_OLLAMA_ENABLED` | `false` | Включить вызов Ollama в `TestGenerator` |
| `BHS_OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | HTTP API; в общей docker-сети с сервисом `ollama` — `http://ollama:11434` |
| `BHS_OLLAMA_MODEL` | `gemma3:1b` | Тег модели |
| `BHS_OLLAMA_TIMEOUT_SEC` | `120` | Таймаут `/api/chat` |
| `BHS_OLLAMA_PULL_TIMEOUT_SEC` | `3600` | Таймаут streaming `/api/pull` при bootstrap |
| `BHS_SKIP_AUTO_OLLAMA` | `false` | Отключить автоподъём/pull |

Вызовы Ollama идут из **процесса bhs на хосте** (не из sandbox с `network none`).

### Автоматизация при `BHS_OLLAMA_ENABLED=true`

1. `GET /api/tags` на `BHS_OLLAMA_BASE_URL`.
2. Если API недоступен — compose для [deploy/docker-compose.llm.yml](../deploy/docker-compose.llm.yml) (нужен `BHS_PROJECT_ROOT` или запуск из checkout).
3. При отсутствии модели — `POST /api/pull`.

Ручной вариант:

```bash
docker compose -f deploy/docker-compose.llm.yml up -d
docker compose -f deploy/docker-compose.llm.yml exec ollama ollama pull gemma3:1b
```

## Запуск `bhs-run` в Docker

Корневой [docker-compose.yml](../docker-compose.yml) собирает образ [`docker/bhs/Dockerfile`](../docker/bhs/Dockerfile) и через **`include`** подмешивает [docker-compose.llm.yml](../deploy/docker-compose.llm.yml) и [docker-compose.observability.yml](../deploy/docker-compose.observability.yml).

| Переменная (хост) | Назначение |
|-------------------|------------|
| `TARGET_REPO` | Путь к анализируемому репо → монтируется в `/repo` |
| `BHS_DOCKER_STATE` | Каталог на хосте для `/workspace/.bhs` (по умолчанию `./.bhs.docker`) |

```bash
docker compose build
docker compose up -d
export TARGET_REPO=/path/to/project
docker compose run --rm bhs
```

Список сервисов: `docker compose config --services`. Отдельные файлы в `deploy/` можно вызывать с `-f` как раньше.

## Мониторинг

| Что | Где |
|-----|-----|
| Итог прогона | stdout: JSON hypervisor |
| Отчёт | артефакты: `BugHunter_Report.md` |
| История шагов | SQLite `BHS_SQLITE_PATH` (по умолчанию `.bhs/state.sqlite`), таблица `audit_log` |
| Метрики | `bhs-run --metrics-port <n>` → `/metrics` |
| Трейсы | `OTEL_EXPORTER_OTLP_ENDPOINT` |

## Полный стек наблюдаемости (порты)

| Сервис | Файл | Порты (пример) |
|--------|------|----------------|
| MinIO, Redis, Prometheus, Grafana, Loki | [deploy/docker-compose.observability.yml](../deploy/docker-compose.observability.yml) | 9000, 6379, 9090, 3000, 3100 |

## Прочие переменные

См. [src/bhs/config.py](../src/bhs/config.py) (`BHS_*`) и [.env.example](../.env.example).
