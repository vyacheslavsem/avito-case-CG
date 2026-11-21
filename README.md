# AI Buyer Assistant

Avito CyberGarden 2026 — hackathon case: create an AI buyer assistant that parses buyer requests, clarifies missing conditions, and selects product kits from a catalog.

## Quick start (CLI)

```sh
# 1. Install dependencies
python3 -m pip install -r requirements.txt

# 2. Set up environment
cp -n .env.example .env
# Edit .env and fill in LLM_API_KEY (get it from @ynwaks on Telegram).
# Export the settings into this Bash session:
set -a
. ./.env
set +a

# 3. Run with the sample catalog
./run --catalog docs/tz/data/catalog.json < docs/tz/examples/01-selection/request.json > response.json
```

## Web interface (FastAPI)

```sh
# 1. Install web dependencies
pip install fastapi uvicorn jinja2 python-multipart

# 2. Set up environment
cp .env.example .env
# Fill in LLM_API_KEY

# 3. Run the web server
python main.py

# 4. Open in browser
# http://localhost:8000 — Каталог товаров
# http://localhost:8000/chat — AI-помощник (чат-бот)
```

### Web UI Features

- **Каталог** — карточки товаров с фильтрами (город, категория, цена)
- **AI-помощник** — чат-бот для подбора товаров через LLM
  - Диалоговый интерфейс с подсказками
  - Отображение подобранных комплектов
  - Поддержка уточняющих вопросов
- **Стилизация** — интерфейс похож на Авито

## Dependencies

- Python 3.10+
- `requests` — for LLM API calls

Install with:
```sh
pip install -r requirements.txt
```

## LLM configuration

The parser sends dialog history to the organizers' Gemma gateway. Catalog
filtering, price calculation and explanations run locally. A gateway error
is reported on stderr and ends the process with a non-zero exit code.
If your shell or the checker already supplies the variables, skip step 2.

Environment variables (read at runtime, never hardcoded):

| Variable | Default | Description |
|---|---|---|
| `LLM_BASE_URL` | `https://sfedu-hackathon-ai-gateway.sfedu-hackathon-ai-gateway.workers.dev/v1` | API endpoint |
| `LLM_MODEL` | `google/gemma-4-31B-it` | Model name |
| `LLM_API_KEY` | _(required)_ | Your team's API key |
| `LLM_USER_AGENT` | `hackathon-team-01/1.0` | Team identifier |

## Usage

```sh
./run --catalog /absolute/path/catalog.json < request.json > response.json
```

- **stdin:** one JSON object with `messages` array
- **stdout:** one JSON object with `status` + variant fields
- **stderr:** logs only
- **exit code:** 0 on success, non-zero on errors

## Statuses

| Status | When |
|---|---|
| `ok` | Full matching kit found (1-3 options) |
| `clarify` | Missing budget, city, or categories |
| `no_match` | Conditions known but no matching kit |

## Testing

```sh
python3 scripts/check.py
```

Runs both organizer examples through the submission entry point. It checks
the status, requested clarification fields and kit constraints. On Windows,
use `python scripts/check.py` from a shell with the same environment variables.

To run the full test suite:

```sh
python3 -m pip install pytest
python3 -m pytest -q
```

Run the live suite sequentially. It shares responses between assertions about
identical inputs and spaces out distinct requests to respect the team quota.

## Project structure

```
run                    executable entry point
main.py                FastAPI веб-сервер
cli_wrapper.py         Обёртка над CLI для вызова из API
src/
  runner.py            stdin/stdout, error handling, pipeline
  parser.py            LLM integration, dialog → structured requirements
  catalog.py           load catalog, filter by city/category/attributes
  combinator.py        build combinations, rank, select up to 3
  validator.py         validate response against catalog and request
  explain.py           generate explanation (template fallback)
templates/             HTML шаблоны (Jinja2)
  base.html            Базовый шаблон с header/footer
  index.html           Страница каталога
  chat.html            Страница чат-бота
static/                Статические файлы
  style.css            CSS стили (Avito-like)
  catalog.js           JS для страницы каталога
  chat.js              JS для чат-бота
tests/                 test cases
scripts/
  check.py             run examples through ./run
schemas/               JSON schemas for validation
data/                  reference data (cities, categories)
docs/tz/               organizer specifications (read-only)
```

## Resources

- [Technical contract](docs/tz/CONTRACT.md) — full API spec
- [LLM API contract](docs/tz/LLM_API.md) — model connection details
- [JSON schemas](schemas/) — request/response validation
- [Examples](docs/tz/examples/) — sample requests and responses
