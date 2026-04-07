"""
Auth service — FastAPI + Authlib OAuth 2.0
Providers: Google, Microsoft, Okta, GitHub
Session: signed JWT in HttpOnly cookie
"""

import os
from datetime import datetime, timedelta, timezone

from authlib.integrations.starlette_client import OAuth, OAuthError
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from httpx import HTTPStatusError
from jose import JWTError, jwt
from starlette.middleware.sessions import SessionMiddleware

load_dotenv()

# ---------------------------------------------------------------------------
# Config (12-factor: all values from environment)
# ---------------------------------------------------------------------------
SECRET_KEY = os.environ["SECRET_KEY"]
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
COOKIE_NAME = "session"
JWT_ALGORITHM = "HS256"
JWT_TTL_HOURS = 8

# ---------------------------------------------------------------------------
# OAuth client registry (Authlib)
# ---------------------------------------------------------------------------
oauth = OAuth()

oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

_ms_tenant = os.getenv("MICROSOFT_TENANT_ID", "common")
oauth.register(
    name="microsoft",
    client_id=os.getenv("MICROSOFT_CLIENT_ID"),
    client_secret=os.getenv("MICROSOFT_CLIENT_SECRET"),
    server_metadata_url=f"https://login.microsoftonline.com/{_ms_tenant}/v2.0/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

_okta_domain = os.getenv("OKTA_DOMAIN", "")
oauth.register(
    name="okta",
    client_id=os.getenv("OKTA_CLIENT_ID"),
    client_secret=os.getenv("OKTA_CLIENT_SECRET"),
    server_metadata_url=(
        f"https://{_okta_domain}/.well-known/openid-configuration"
        if _okta_domain
        else None
    ),
    client_kwargs={"scope": "openid email profile"},
)

oauth.register(
    name="github",
    client_id=os.getenv("GITHUB_CLIENT_ID"),
    client_secret=os.getenv("GITHUB_CLIENT_SECRET"),
    access_token_url="https://github.com/login/oauth/access_token",
    authorize_url="https://github.com/login/oauth/authorize",
    api_base_url="https://api.github.com/",
    client_kwargs={"scope": "read:user user:email"},
)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Auth")

# SessionMiddleware is required by Authlib to store the OAuth state/nonce
# between the login redirect and the return callback.
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)


# ---------------------------------------------------------------------------
# JWT cookie helpers
# ---------------------------------------------------------------------------
def _create_jwt(user: dict) -> str:
    payload = {
        "sub": user.get("email") or user.get("login") or user.get("id", ""),
        "name": user.get("name", ""),
        "email": user.get("email", ""),
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_TTL_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)


def _decode_jwt(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None


def _current_user(request: Request) -> dict | None:
    token = request.cookies.get(COOKIE_NAME)
    return _decode_jwt(token) if token else None


def _set_cookie(response: RedirectResponse, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=BASE_URL.startswith("https"),
        samesite="lax",
        max_age=JWT_TTL_HOURS * 3600,
    )


def _remove_cookie(response: RedirectResponse) -> None:
    response.delete_cookie(key=COOKIE_NAME, httponly=True, samesite="lax")


# ---------------------------------------------------------------------------
# Central authenticate helper — exchanges provider token for a user dict
# ---------------------------------------------------------------------------
async def authenticate(provider: str, request: Request) -> dict:
    client = oauth.create_client(provider)
    token = await client.authorize_access_token(request)

    if provider == "github":
        resp = await client.get("user", token=token)
        resp.raise_for_status()
        user = resp.json()
        if not user.get("email"):
            emails_resp = await client.get("user/emails", token=token)
            emails_resp.raise_for_status()
            primary = next((e for e in emails_resp.json() if e.get("primary")), None)
            user["email"] = primary["email"] if primary else ""
    else:
        user = token.get("userinfo") or {}
        if not user and "id_token" in token:
            user = await client.parse_id_token(request, token)

    return user


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Tell the user whether they are logged in or not."""
    user = _current_user(request)
    if user:
        name = user.get("name") or user.get("email") or "user"
        body = (
            f"<p>Logged in as <strong>{name}</strong> ({user.get('email', '')})</p>"
            f'<p><a href="/auth/logout">Log out</a></p>'
        )
    else:
        body = (
            "<p>Not logged in.</p>"
            "<ul>"
            '<li><a href="/auth/google/login">Log in with Google</a></li>'
            '<li><a href="/auth/microsoft/login">Log in with Microsoft</a></li>'
            '<li><a href="/auth/okta/login">Log in with Okta</a></li>'
            '<li><a href="/auth/github/login">Log in with GitHub</a></li>'
            "</ul>"
        )
    return HTMLResponse(f"<html><body>{body}</body></html>")


# -- Google ------------------------------------------------------------------


@app.get("/auth/google/login")
async def google_login(request: Request):
    """Redirect into Google OAuth 2.0 workflow."""
    redirect_uri = f"{BASE_URL}/auth/google/return"
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get("/auth/google/return")
async def google_return(request: Request):
    """Verify Google OAuth 2.0 response, set cookie, redirect to /."""
    try:
        user = await authenticate("google", request)
    except OAuthError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    token = _create_jwt(user)
    response = RedirectResponse(url="/", status_code=303)
    _set_cookie(response, token)
    return response


# -- Microsoft ---------------------------------------------------------------


@app.get("/auth/microsoft/login")
async def microsoft_login(request: Request):
    """Redirect into Microsoft OAuth 2.0 workflow."""
    redirect_uri = f"{BASE_URL}/auth/microsoft/return"
    return await oauth.microsoft.authorize_redirect(request, redirect_uri)


@app.get("/auth/microsoft/return")
async def microsoft_return(request: Request):
    """Verify Microsoft OAuth 2.0 response, set cookie, redirect to /."""
    try:
        user = await authenticate("microsoft", request)
    except OAuthError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    token = _create_jwt(user)
    response = RedirectResponse(url="/", status_code=303)
    _set_cookie(response, token)
    return response


# -- Okta --------------------------------------------------------------------


@app.get("/auth/okta/login")
async def okta_login(request: Request):
    """Redirect into Okta OAuth 2.0 workflow."""
    redirect_uri = f"{BASE_URL}/auth/okta/return"
    try:
        return await oauth.okta.authorize_redirect(request, redirect_uri)
    except HTTPStatusError as exc:
        return JSONResponse(
            {"error": f"Okta metadata fetch failed: {exc}"}, status_code=502
        )


@app.get("/auth/okta/return")
async def okta_return(request: Request):
    """Verify Okta OAuth 2.0 response, set cookie, redirect to /."""
    try:
        user = await authenticate("okta", request)
    except OAuthError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    token = _create_jwt(user)
    response = RedirectResponse(url="/", status_code=303)
    _set_cookie(response, token)
    return response


# -- GitHub ------------------------------------------------------------------


@app.get("/auth/github/login")
async def github_login(request: Request):
    """Redirect into GitHub OAuth 2.0 workflow."""
    redirect_uri = f"{BASE_URL}/auth/github/return"
    return await oauth.github.authorize_redirect(request, redirect_uri)


@app.get("/auth/github/return")
async def github_return(request: Request):
    """Verify GitHub OAuth 2.0 response, set cookie, redirect to /."""
    try:
        user = await authenticate("github", request)
    except OAuthError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    token = _create_jwt(user)
    response = RedirectResponse(url="/", status_code=303)
    _set_cookie(response, token)
    return response


# -- Logout ------------------------------------------------------------------


@app.get("/auth/logout")
async def logout():
    """Remove session cookie and redirect to /."""
    response = RedirectResponse(url="/", status_code=303)
    _remove_cookie(response)
    return response
