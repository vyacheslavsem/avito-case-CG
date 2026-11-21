"""
FastAPI приложение — веб-обёртка над CLI-утилитой.
Отдаёт HTML-страницы + API endpoints для AJAX.
"""

import json
from pathlib import Path

import jinja2
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from cli_wrapper import call_cli

app = FastAPI(title="Avito CyberGarden — AI Buyer Assistant")

BASE_DIR = Path(__file__).parent

# Mount static files
static_dir = BASE_DIR / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Templates dir — используем jinja2 напрямую с UTF-8
templates_dir = BASE_DIR / "templates"

# FileSystemLoader на Windows может использовать CP1251 — явно указываем UTF-8
class UTF8FileSystemLoader(jinja2.BaseLoader):
    def __init__(self, path: str):
        self.path = path
    
    def get_source(self, environment, template):
        # Убираем .html если не указан
        if not template.endswith('.html'):
            template = template + '.html'
        filepath = self.path + "/" + template
        full_path = Path(self.path) / template
        if not full_path.exists():
            raise jinja2.TemplateNotFound(template)
        with open(full_path, "r", encoding="utf-8") as f:
            source = f.read()
        return source, filepath, lambda: True

_jinja_env = jinja2.Environment(
    loader=UTF8FileSystemLoader(str(templates_dir)),
    autoescape=True,
)


def render_template(filename: str, context: dict) -> str:
    """Рендерит Jinja2 шаблон в строку."""
    template = _jinja_env.get_template(filename)
    return template.render(**context)


# ------------------------------------------------------------------ #
#                         PAGE ROUTES                                #
# ------------------------------------------------------------------ #

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Главная страница — каталог товаров."""
    html = render_template("index.html", {"page": "index"})
    return HTMLResponse(content=html, media_type="text/html; charset=utf-8")


@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    """Страница чат-бота для подбора товаров."""
    html = render_template("chat.html", {"page": "chat"})
    return HTMLResponse(content=html, media_type="text/html; charset=utf-8")


# ------------------------------------------------------------------ #
#                        API ROUTES                                  #
# ------------------------------------------------------------------ #

@app.post("/api/chat")
async def chat_api(request: Request):
    """
    Основной endpoint для чат-бота.
    
    Body: { "messages": [{"role": "user", "text": "..."}, ...] }
    Returns: { "status": "ok"|"clarify"|"no_match", ... }
    """
    body = await request.json()
    messages = body.get("messages", [])

    if not messages:
        return {"error": "messages is required"}

    # Последнее сообщение должно быть от пользователя
    last_msg = messages[-1]
    if last_msg.get("role") != "user":
        return {"error": "Last message must be from user"}

    try:
        result = call_cli(messages=messages)
        return result
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/catalog", response_class=HTMLResponse)
async def catalog_api(request: Request):
    """
    Получить товары из каталога с фильтрами.
    
    Query params: city, category, min_price, max_price
    """
    city = request.query_params.get("city")
    category = request.query_params.get("category")
    min_price = request.query_params.get("min_price", type=float)
    max_price = request.query_params.get("max_price", type=float)

    catalog_path = BASE_DIR / "data" / "catalog.json"
    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    listings = catalog.get("listings", catalog if isinstance(catalog, list) else [])

    filtered = []
    for item in listings:
        if city and item.get("city_id") != city:
            continue
        if category and item.get("category") != category:
            continue
        price = item.get("price_rub", 0)
        if min_price is not None and price < min_price:
            continue
        if max_price is not None and price > max_price:
            continue
        filtered.append(item)

    cats_path = BASE_DIR / "data" / "categories.json"
    with open(cats_path, "r", encoding="utf-8") as f:
        categories = json.load(f)

    return {
        "listings": filtered,
        "categories": categories.get("categories", categories if isinstance(categories, list) else []),
    }


@app.get("/api/cities")
async def cities_api():
    """Получить список городов."""
    cities_path = BASE_DIR / "data" / "cities.json"
    try:
        with open(cities_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        cities = data if isinstance(data, list) else data.get("cities", [])
    except FileNotFoundError:
        # Fallback: попробуем catalog.json
        catalog_path = BASE_DIR / "data" / "catalog.json"
        with open(catalog_path, "r", encoding="utf-8") as f:
            catalog = json.load(f)
        listings = catalog.get("listings", [])
        cities = list(set(item.get("city_id") for item in listings if item.get("city_id")))
    return cities


@app.get("/api/categories")
async def categories_api():
    """Получить список категорий."""
    cats_path = BASE_DIR / "data" / "categories.json"
    try:
        with open(cats_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        categories = data.get("categories", data if isinstance(data, list) else [])
    except FileNotFoundError:
        categories = []
    return categories


# ------------------------------------------------------------------ #
#                        MAIN ENTRY                                  #
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
