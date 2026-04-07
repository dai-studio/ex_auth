"""
E2E route validation — validates all routes respond appropriately.
Tests run against the ASGI app directly via httpx.AsyncClient (no live server needed).
"""

import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Provide a minimal env so the app can be imported without real OAuth credentials
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test")
os.environ.setdefault("MICROSOFT_CLIENT_ID", "test")
os.environ.setdefault("MICROSOFT_CLIENT_SECRET", "test")
os.environ.setdefault("OKTA_CLIENT_ID", "test")
os.environ.setdefault("OKTA_CLIENT_SECRET", "test")
os.environ.setdefault("OKTA_DOMAIN", "test.okta.com")
os.environ.setdefault("GITHUB_CLIENT_ID", "test")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test")
os.environ.setdefault("BASE_URL", "http://testserver")

from main import app, COOKIE_NAME, SECRET_KEY, _create_jwt  # noqa: E402


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# / — root endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_index_not_logged_in(client: AsyncClient):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "Not logged in" in resp.text


@pytest.mark.asyncio
async def test_index_logged_in(client: AsyncClient):
    token = _create_jwt({"email": "user@example.com", "name": "Test User"})
    resp = await client.get("/", cookies={COOKIE_NAME: token})
    assert resp.status_code == 200
    assert "user@example.com" in resp.text


# ---------------------------------------------------------------------------
# Login redirects — each provider's /login route must redirect (302/303)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path,expected_statuses",
    [
        ("/auth/google/login", (302, 303)),
        ("/auth/microsoft/login", (302, 303)),
        # Okta fetches OIDC discovery at login time; with a fake domain it returns 502
        ("/auth/okta/login", (302, 303, 502)),
        ("/auth/github/login", (302, 303)),
    ],
)
async def test_login_routes_redirect(
    client: AsyncClient, path: str, expected_statuses: tuple
):
    resp = await client.get(path, follow_redirects=False)
    assert (
        resp.status_code in expected_statuses
    ), f"{path} returned {resp.status_code}, expected one of {expected_statuses}"
    # For real redirects (not error responses), verify Location header is present
    if resp.status_code in (302, 303):
        assert resp.headers.get("location"), f"{path} redirect has no Location header"


# ---------------------------------------------------------------------------
# Return endpoints — called without a valid state should return 400
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/auth/google/return",
        "/auth/microsoft/return",
        "/auth/okta/return",
        "/auth/github/return",
    ],
)
async def test_return_routes_without_state(client: AsyncClient, path: str):
    resp = await client.get(path, follow_redirects=False)
    # Without a valid OAuth state, Authlib raises OAuthError → we return 400
    assert (
        resp.status_code == 400
    ), f"{path} returned {resp.status_code}, expected 400 (no OAuth state)"


# ---------------------------------------------------------------------------
# /auth/logout — must remove cookie and redirect to /
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_logout_removes_cookie_and_redirects(client: AsyncClient):
    token = _create_jwt({"email": "user@example.com", "name": "Test User"})
    resp = await client.get(
        "/auth/logout",
        cookies={COOKIE_NAME: token},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303, 307)
    assert resp.headers.get("location") == "/"
    # Cookie should be cleared (max-age=0 or explicit deletion)
    set_cookie = resp.headers.get("set-cookie", "")
    assert COOKIE_NAME in set_cookie
    assert (
        "max-age=0" in set_cookie.lower()
        or 'expires="thu, 01 jan 1970' in set_cookie.lower()
    )
