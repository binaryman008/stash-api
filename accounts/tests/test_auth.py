from rest_framework.test import APIClient

from accounts.tests.factories import PASSWORD

ME = "/api/auth/me/"
LOGIN = "/api/auth/login/"
LOGOUT = "/api/auth/logout/"


def credentials(user, password=PASSWORD):
    return {"username": user.username, "password": password}


# --- /me ---------------------------------------------------------------------


def test_me_returns_null_user_and_sets_csrf_cookie_when_logged_out(anon, db):
    r = anon.get(ME)

    assert r.status_code == 200
    assert r.json() == {"user": None}
    assert "csrftoken" in r.cookies


def test_me_returns_current_user(api, user):
    r = api.get(ME)

    assert r.status_code == 200
    assert r.json()["user"] == {"id": user.id, "username": user.username, "email": user.email}


# --- login -------------------------------------------------------------------


def test_login_with_valid_credentials_starts_a_session(user):
    client = APIClient()

    r = client.post(LOGIN, credentials(user), format="json")

    assert r.status_code == 200
    assert r.json()["username"] == user.username
    assert "password" not in r.json()
    assert "sessionid" in r.cookies
    # The session cookie alone is now enough to use the API.
    assert client.get("/api/links/").status_code == 200


def test_login_with_wrong_password_is_rejected(anon, user):
    r = anon.post(LOGIN, credentials(user, password="wrong"), format="json")

    assert r.status_code == 400
    assert "sessionid" not in r.cookies


def test_login_requires_username_and_password(anon, db):
    r = anon.post(LOGIN, {}, format="json")

    assert r.status_code == 400
    assert set(r.json()) == {"username", "password"}


def test_login_rejects_requests_without_csrf_token(user):
    client = APIClient(enforce_csrf_checks=True)

    r = client.post(LOGIN, credentials(user), format="json")

    assert r.status_code == 403


def test_login_accepts_csrf_token_from_me_endpoint(user):
    """The exact flow the React app uses: GET /me for the cookie, send it back as a header."""
    client = APIClient(enforce_csrf_checks=True)
    client.get(ME)
    token = client.cookies["csrftoken"].value

    r = client.post(LOGIN, credentials(user), format="json", HTTP_X_CSRFTOKEN=token)

    assert r.status_code == 200


def test_login_is_rate_limited_after_five_attempts(user):
    client = APIClient()
    for _ in range(5):
        r = client.post(LOGIN, credentials(user, password="wrong"), format="json")
        assert r.status_code == 400

    # Even the correct password is refused once the limit is hit.
    r = client.post(LOGIN, credentials(user), format="json")

    assert r.status_code == 429


# --- logout ------------------------------------------------------------------


def test_logout_ends_the_session(user):
    client = APIClient()
    client.force_login(user)
    assert client.get(ME).json()["user"]["username"] == user.username

    r = client.post(LOGOUT)

    assert r.status_code == 204
    assert client.get(ME).json() == {"user": None}


def test_logout_requires_login(anon, db):
    assert anon.post(LOGOUT).status_code == 403
