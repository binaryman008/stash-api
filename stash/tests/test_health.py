import pytest

from stash import health


class _BrokenConnection:
    def cursor(self):
        raise RuntimeError("database is down")


class _BrokenCache:
    def set(self, *args, **kwargs):
        raise ConnectionError("redis is down")

    def get(self, *args, **kwargs):
        raise ConnectionError("redis is down")


def test_healthz_is_ok_without_touching_dependencies(client, monkeypatch):
    # Liveness must not depend on the database or cache.
    monkeypatch.setattr(health, "connection", _BrokenConnection())
    monkeypatch.setattr(health, "cache", _BrokenCache())

    r = client.get("/healthz")

    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.django_db
def test_readyz_is_ok_when_dependencies_are_up(client):
    r = client.get("/readyz")

    assert r.status_code == 200
    assert r.json() == {"status": "ok", "checks": {"database": "ok", "cache": "ok"}}


@pytest.mark.django_db
def test_readyz_fails_when_database_is_down(client, monkeypatch):
    monkeypatch.setattr(health, "connection", _BrokenConnection())

    r = client.get("/readyz")

    assert r.status_code == 503
    assert r.json() == {"status": "error", "checks": {"database": "error", "cache": "ok"}}


@pytest.mark.django_db
def test_readyz_fails_when_cache_is_down(client, monkeypatch):
    monkeypatch.setattr(health, "cache", _BrokenCache())

    r = client.get("/readyz")

    assert r.status_code == 503
    assert r.json() == {"status": "error", "checks": {"database": "ok", "cache": "error"}}


def test_health_endpoints_do_not_require_login(client, db):
    assert client.get("/healthz").status_code == 200
    assert client.get("/readyz").status_code == 200
