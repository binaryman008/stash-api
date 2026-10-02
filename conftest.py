import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from accounts.tests.factories import UserFactory


@pytest.fixture(autouse=True)
def _isolated_cache(settings):
    """Use an in-memory cache per test so throttle counters never leak between tests
    and the suite doesn't depend on (or pollute) your local Redis."""
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    cache.clear()


@pytest.fixture
def user(db):
    return UserFactory()


@pytest.fixture
def other_user(db):
    return UserFactory()


@pytest.fixture
def api(user):
    """API client already authenticated as `user`."""
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def anon():
    return APIClient()
