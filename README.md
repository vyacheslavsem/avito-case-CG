# AI Buyer Assistant

Avito CyberGarden 2026 — hackathon case: create an AI buyer assistant that parses buyer requests, clarifies missing conditions, and selects product kits from a catalog.

## Quick start

```sh
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up environment
cp .env.example .env
# Fill in LLM_API_KEY (get from @ynwaks on Telegram)

# 3. Run with the sample catalog
./run --catalog docs/tz/data/catalog.json < docs/tz/examples/01-selection/request.json > response.json
```

## Dependencies

- Python 3.10+
- `requests` — for LLM API calls

Install with:
```sh
pip install -r requirements.txt
```

## LLM configuration

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
python scripts/check.py
```

Runs all examples through `./run` and validates responses.

## Project structure

```
run                    executable entry point
src/
  runner.py            stdin/stdout, error handling, pipeline
  parser.py            LLM integration, dialog → structured requirements
  catalog.py           load catalog, filter by city/category/attributes
  combinator.py        build combinations, rank, select up to 3
  validator.py         validate response against catalog and request
  explain.py           generate explanation (template fallback)
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
