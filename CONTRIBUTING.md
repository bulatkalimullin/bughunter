# Contributing to BugHunter Swarm

Спасибо за интерес к проекту. Ниже — минимальный цикл для локальной разработки и проверки PR.

## Окружение

Рекомендуется **Python 3.11+**.

### pip / venv

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### uv (альтернатива)

```bash
uv venv .venv && source .venv/bin/activate
uv sync --extra dev
```

Скопируйте [.env.example](.env.example) в `.env` и при необходимости задайте `BHS_REPO_PATH`, `BHS_MAX_ITERATIONS`, флаги bootstrap (`BHS_AUTO_*`). Файл `.env` не коммитьте.

## Качество кода

```bash
ruff check src tests
pytest tests/ -q
# или
uv run ruff check src tests
uv run pytest tests/ -q
```

## Запуск BHS без Docker

Для быстрой проверки графа и CI:

```bash
BHS_SANDBOX_MODE=local bhs-run --repo .
```

## Docker

- **Корневой стек:** [docker-compose.yml](docker-compose.yml) — образ `bhs` и `include` сервисов из `deploy/`. После `docker compose up -d` держите **`BHS_AUTO_OBSERVABILITY=false`** в `.env`, если observability уже поднят этим compose (иначе bootstrap при `bhs-run` может конфликтовать по портам).
- **Только Ollama / только observability:** по-прежнему `docker compose -f deploy/docker-compose.llm.yml` и т.д.

## Архитектура и окружение

- [docs/BHS_IMPLEMENTATION.md](docs/BHS_IMPLEMENTATION.md) — DAG, чеклист, backlog.
- [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md) — переменные, bootstrap, итерации, compose.
- [.env.example](.env.example) — шаблон переменных.

## Pull requests

Шаблон — [`.github/pull_request_template.md`](.github/pull_request_template.md). Опишите изменение; для кода приложите вывод `ruff` и `pytest`; если менялись Docker/compose — кратко опишите сценарий запуска.
