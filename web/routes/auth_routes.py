"""Login / logout routes."""

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from core.config import env
from web.auth import COOKIE_NAME, create_session_token, verify_code_word

router = APIRouter()


@router.get("/login")
async def login_page(request: Request, error: str | None = None):
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": error},
    )


@router.post("/login")
async def login_submit(request: Request, code: str = Form(...)):
    role = verify_code_word(code)
    if role is None:
        templates = request.app.state.templates
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Неверное кодовое слово"},
            status_code=401,
        )

    token = create_session_token(role)
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=env.web_cookie_ttl_days * 86400,
        httponly=True,
        samesite="strict",
        secure=env.web_cookie_secure,
    )
    return response


@router.post("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(key=COOKIE_NAME)
    return response
