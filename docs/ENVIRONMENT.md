# Окружение BugHunter Swarm

## Минимальное (без внешних сервисов)

| Компонент | Нужно |
|-----------|--------|
| Python | 3.11+ |
| Зависимости | `pip install -e ".[dev]"` |
| Sandbox | `BHS_SANDBOX_MODE=local` (subprocess на хосте) |
| Цель анализа | `BHS_REPO_PATH` или аргумент `bhs-run --repo` (флаг важнее env) |

Команда:

```bash
BHS_SANDBOX_MODE=local bhs-run --repo .
```

Либо задайте репозиторий в окружении:

```bash
export BHS_REPO_PATH=/path/to/project-under-test
BHS_SANDBOX_MODE=local bhs-run
```

## Итерации feedback-loop и ранний выход по багам

| Переменная | По умолчанию | Описание |
|------------|----------------|----------|
| `BHS_MAX_ITERATIONS` | `1` | Сколько раз может крутиться цикл `bug_logger` → `feedback_tick` → `test_generator` → … (до `5000`) |
| `BHS_STOP_BUG_COUNT` | `0` | Если `>0`, после dedupe в `bug_logger` при `len(bugs) >=` порога выполняется `finalize`, даже если итераций осталось. **Внимание:** статический анализ может сразу дать много находок — цикл завершится после первого `bug_logger`, если dedupe-список уже ≥ порога. |
| `BHS_SANDBOX_CPU_BUDGET_SECONDS` | (авто) | Лимит `cpu_seconds` в `sandbox_limits` для [`check_quotas`](../src/bhs/hypervisor/router.py). Если не задан: `max(120, 3 * BHS_MAX_ITERATIONS)` секунд. |

## Ollama (LLM для генерации тестов)

| Переменная | По умолчанию | Описание |
|------------|----------------|----------|
| `BHS_OLLAMA_ENABLED` | `false` | Включить вызов Ollama в `TestGenerator` |
| `BHS_OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | HTTP API Ollama |
| `BHS_OLLAMA_MODEL` | `gemma3:1b` | Тег модели |
| `BHS_OLLAMA_TIMEOUT_SEC` | `120` | Таймаут запроса `/api/chat` |
| `BHS_OLLAMA_PULL_TIMEOUT_SEC` | `3600` | Таймаут streaming `/api/pull` при автозагрузке модели |
| `BHS_SKIP_AUTO_OLLAMA` | `false` | Не поднимать compose и не делать `pull`, если Ollama уже у вас |

Вызовы Ollama идут из **процесса bhs на хосте** (не из sandbox-контейнера с `network none`).

### Автоматизация при `bhs-run`

Если `BHS_OLLAMA_ENABLED=true` и `BHS_SKIP_AUTO_OLLAMA` не задан:

1. Запрос `GET /api/tags` на `BHS_OLLAMA_BASE_URL`.
2. Если API недоступен — `docker compose` / `podman compose` для [deploy/docker-compose.llm.yml](../deploy/docker-compose.llm.yml) (нужен каталог репозитория с `deploy/`; при запуске не из checkout задайте `BHS_PROJECT_ROOT`).
3. Если модели нет в списке — `POST /api/pull` для `BHS_OLLAMA_MODEL`.

Ручной вариант без автоматики:

```bash
docker compose -f deploy/docker-compose.llm.yml up -d
docker compose -f deploy/docker-compose.llm.yml exec ollama ollama pull gemma3:1b
```

На Linux при `bhs-run` на хосте и Ollama в Docker используйте `BHS_OLLAMA_BASE_URL=http://127.0.0.1:11434` при проброшенном порте `11434`.

## Автосборка sandbox-образа и observability

| Переменная | По умолчанию | Описание |
|------------|----------------|----------|
| `BHS_AUTO_SANDBOX_IMAGE` | `false` | Если не `BHS_SANDBOX_MODE=local`, перед запуском выполнить `docker build` / `podman build`, когда образ `BHS_SANDBOX_IMAGE` отсутствует |
| `BHS_AUTO_OBSERVABILITY` | `false` | Поднять [docker-compose.observability.yml](../deploy/docker-compose.observability.yml) (`up -d`) |
| `BHS_PROJECT_ROOT` | — | Абсолютный путь к корню репозитория (где лежит `deploy/docker-compose.llm.yml`) |

Для compose используется тот же runtime, что и для sandbox: при `BHS_CONTAINER_RUNTIME=podman` вызывается `podman compose`.

## Запуск bhs-run в Docker

Корневой [docker-compose.yml](../docker-compose.yml) объединяет **bhs** с сервисами из `deploy/` через директиву **`include`**: [docker-compose.llm.yml](../deploy/docker-compose.llm.yml) (Ollama) и [docker-compose.observability.yml](../deploy/docker-compose.observability.yml) (MinIO, Redis, Prometheus, Grafana, Loki). Список: `docker compose config --services`.

```bash
docker compose build
docker compose up -d
export TARGET_REPO=/path/to/project
docker compose run --rm bhs
```

Отдельные файлы в `deploy/` по-прежнему можно вызывать сами по себе (`docker compose -f deploy/...`). В корневом проекте для LLM внутри сети compose задайте `BHS_OLLAMA_BASE_URL=http://ollama:11434`.

## Полный стек наблюдаемости и артефактов

| Сервис | Файл | Порты (пример) |
|--------|------|----------------|
| MinIO, Redis, Prometheus, Grafana, Loki | [deploy/docker-compose.observability.yml](../deploy/docker-compose.observability.yml) | 9000, 6379, 9090, 3000, 3100 |

## Прочие переменные

См. [src/bhs/config.py](../src/bhs/config.py) (`BHS_*`) и корневой [.env.example](../.env.example).
