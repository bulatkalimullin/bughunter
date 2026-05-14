# Окружение BugHunter Swarm

## Минимальное (без внешних сервисов)

| Компонент | Нужно |
|-----------|--------|
| Python | 3.11+ |
| Зависимости | `pip install -e ".[dev]"` |
| Sandbox | `BHS_SANDBOX_MODE=local` (subprocess на хосте) |

Команда:

```bash
BHS_SANDBOX_MODE=local bhs-run --repo .
```

## Ollama (LLM для генерации тестов)

| Переменная | По умолчанию | Описание |
|------------|----------------|----------|
| `BHS_OLLAMA_ENABLED` | `false` | Включить вызов Ollama в `TestGenerator` |
| `BHS_OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | HTTP API Ollama |
| `BHS_OLLAMA_MODEL` | `gemma3:1b` | Тег модели |
| `BHS_OLLAMA_TIMEOUT_SEC` | `120` | Таймаут запроса |

Вызовы Ollama идут из **процесса bhs на хосте** (не из sandbox-контейнера с `network none`).

Docker: см. [deploy/docker-compose.llm.yml](../deploy/docker-compose.llm.yml). После первого запуска:

```bash
docker compose -f deploy/docker-compose.llm.yml exec ollama ollama pull gemma3:1b
```

На Linux при `bhs-run` на хосте и Ollama в Docker используйте `BHS_OLLAMA_BASE_URL=http://127.0.0.1:11434` при проброшенном порте `11434`.

## Полный стек наблюдаемости и артефактов

| Сервис | Файл | Порты (пример) |
|--------|------|----------------|
| MinIO, Redis, Prometheus, Grafana, Loki | [deploy/docker-compose.observability.yml](../deploy/docker-compose.observability.yml) | 9000, 6379, 9090, 3000, 3100 |

## Прочие переменные

См. [src/bhs/config.py](../src/bhs/config.py) (`BHS_*`) и корневой [.env.example](../.env.example).
