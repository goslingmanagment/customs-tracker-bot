"""FastAPI application factory."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from web.context import register_filters

WEB_DIR = Path(__file__).resolve().parent


def create_app() -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None)

    # Static files
    app.mount(
        "/static",
        StaticFiles(directory=WEB_DIR / "static"),
        name="static",
    )

    # Jinja2 templates
    templates = Jinja2Templates(directory=WEB_DIR / "templates")
    register_filters(templates.env)

    # Store templates on app state for route access
    app.state.templates = templates

    # --- Error handlers ---

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        if exc.status_code == 404:
            return templates.TemplateResponse(
                "error.html",
                {"request": request, "code": 404, "message": "Страница не найдена"},
                status_code=404,
            )
        if exc.status_code == 403:
            return templates.TemplateResponse(
                "error.html",
                {"request": request, "code": 403, "message": "Недостаточно прав"},
                status_code=403,
            )
        # For 401, redirect to login
        if exc.status_code == 401:
            return RedirectResponse(url="/login", status_code=302)
        return HTMLResponse(
            content=f"Error {exc.status_code}: {exc.detail}",
            status_code=exc.status_code,
        )

    # --- Register routes ---
    from web.routes.auth_routes import router as auth_router
    from web.routes.dashboard import router as dashboard_router
    from web.routes.stats import router as stats_router
    from web.routes.tasks import router as tasks_router

    app.include_router(auth_router)
    app.include_router(dashboard_router)
    app.include_router(tasks_router)
    app.include_router(stats_router)

    return app
