# Contributing to BugHunter Swarm

Спасибо за интерес к проекту. Ниже — минимальный цикл для локальной разработки.

## Окружение

Рекомендуется Python 3.11+.

### pip / venv

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### uv (альтернатива)

```bash
uv venv .venv && source .venv/bin/activate
uv pip install -e ".[dev]"
```

## Качество кода

```bash
ruff check src tests
pytest -q
```

## Запуск BHS без Docker

Для быстрой проверки графа и CI используйте локальный режим песочницы:

```bash
BHS_SANDBOX_MODE=local bhs-run --repo .
```

## Архитектура и backlog

См. [docs/BHS_IMPLEMENTATION.md](docs/BHS_IMPLEMENTATION.md): DAG, чеклист реализованного и оставшейся работы.

## Pull requests

Краткий шаблон запроса на слияние — в [`.github/pull_request_template.md`](.github/pull_request_template.md). Опишите изменение, приложите вывод `ruff` и `pytest`, если менялся код.
