from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from links.models import Link
from links.tests.factories import LinkFactory, TagFactory

LINKS = "/api/links/"


def detail(link):
    return f"{LINKS}{link.id}/"


# --- auth --------------------------------------------------------------------


@pytest.mark.parametrize("path", [LINKS, "/api/tags/", "/api/stats/"])
def test_endpoints_require_login(anon, db, path):
    # Session-only auth: DRF answers unauthenticated requests with 403, not 401.
    assert anon.get(path).status_code == 403


# --- create ------------------------------------------------------------------


def test_create_link_starts_pending_and_belongs_to_the_user(api, user):
    r = api.post(LINKS, {"url": "https://docs.djangoproject.com"}, format="json")

    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "pending"
    assert body["tags"] == []
    assert Link.objects.get(id=body["id"]).owner == user


def test_create_link_normalises_and_dedupes_tags(api):
    r = api.post(
        LINKS,
        {"url": "https://example.com", "tags": ["Django", "django ", "AWS"]},
        format="json",
    )

    assert r.status_code == 201
    assert r.json()["tags"] == ["aws", "django"]


def test_create_link_rejects_blank_tags(api):
    r = api.post(LINKS, {"url": "https://example.com", "tags": ["django", "  "]}, format="json")

    assert r.status_code == 400
    assert r.json()["tags"] == {"1": ["This field may not be blank."]}
    assert not Link.objects.exists()


def test_create_link_ignores_read_only_fields(api):
    r = api.post(
        LINKS,
        {"url": "https://example.com", "status": "ready", "title": "Hacked", "reading_minutes": 9},
        format="json",
    )

    assert r.status_code == 201
    assert r.json()["status"] == "pending"
    assert r.json()["title"] == ""
    assert r.json()["reading_minutes"] is None


def test_create_link_rejects_invalid_url(api):
    r = api.post(LINKS, {"url": "not-a-url"}, format="json")

    assert r.status_code == 400
    assert "url" in r.json()


def test_create_link_rejects_duplicate_url_for_same_user(api):
    api.post(LINKS, {"url": "https://example.com"}, format="json")

    r = api.post(LINKS, {"url": "https://example.com"}, format="json")

    assert r.status_code == 400
    assert r.json()["url"] == ["You already saved this link."]


def test_different_users_can_save_the_same_url(api, other_user):
    LinkFactory(owner=other_user, url="https://example.com")

    r = api.post(LINKS, {"url": "https://example.com"}, format="json")

    assert r.status_code == 201


# --- list / retrieve ---------------------------------------------------------


def test_list_shows_only_my_links_newest_first(api, user, other_user):
    now = timezone.now()
    older = LinkFactory(owner=user)
    newer = LinkFactory(owner=user)
    Link.objects.filter(id=older.id).update(created_at=now - timedelta(days=1))
    Link.objects.filter(id=newer.id).update(created_at=now)
    LinkFactory(owner=other_user)

    r = api.get(LINKS)

    assert r.status_code == 200
    assert r.json()["count"] == 2
    assert [link["id"] for link in r.json()["results"]] == [newer.id, older.id]


def test_list_is_paginated_20_per_page(api, user):
    LinkFactory.create_batch(25, owner=user)

    page1 = api.get(LINKS).json()
    page2 = api.get(LINKS, {"page": 2}).json()

    assert page1["count"] == 25
    assert len(page1["results"]) == 20
    assert page1["next"] is not None
    assert len(page2["results"]) == 5
    assert page2["next"] is None


def test_filter_by_tag_is_case_insensitive(api, user):
    tagged = LinkFactory(owner=user)
    tagged.tags.add(TagFactory(owner=user, name="aws"))
    LinkFactory(owner=user)

    r = api.get(LINKS, {"tag": "AWS"})

    assert [link["id"] for link in r.json()["results"]] == [tagged.id]


@pytest.mark.parametrize("query", ["django", "KUBERNETES", "react.dev"])
def test_search_matches_title_description_or_url(api, user, query):
    LinkFactory(owner=user, title="Deploying Django on ECS")
    LinkFactory(owner=user, description="All about Kubernetes probes")
    LinkFactory(owner=user, url="https://react.dev/learn")
    LinkFactory(owner=user, title="Unrelated")

    r = api.get(LINKS, {"q": query})

    assert r.json()["count"] == 1


def test_search_never_returns_other_users_links(api, other_user):
    LinkFactory(owner=other_user, title="Django secrets")

    assert api.get(LINKS, {"q": "django"}).json()["count"] == 0


def test_list_query_count_does_not_grow_with_number_of_links(api, user):
    """Guards against N+1 queries: tags must be prefetched, not loaded per link."""

    def queries_for_list():
        with CaptureQueriesContext(connection) as ctx:
            assert api.get(LINKS).status_code == 200
        return len(ctx.captured_queries)

    for _ in range(2):
        LinkFactory(owner=user).tags.add(TagFactory(owner=user))
    few = queries_for_list()

    for _ in range(10):
        LinkFactory(owner=user).tags.add(TagFactory(owner=user))

    assert queries_for_list() == few


def test_retrieve_my_link(api, user):
    link = LinkFactory(owner=user, title="Mine")

    r = api.get(detail(link))

    assert r.status_code == 200
    assert r.json()["title"] == "Mine"


# --- other users' links are invisible (404, not 403, so ids don't leak) ------


def test_cannot_retrieve_another_users_link(api, other_user):
    assert api.get(detail(LinkFactory(owner=other_user))).status_code == 404


def test_cannot_update_another_users_link(api, other_user):
    link = LinkFactory(owner=other_user)

    r = api.patch(detail(link), {"tags": ["mine-now"]}, format="json")

    assert r.status_code == 404
    assert link.tags.count() == 0


def test_cannot_delete_another_users_link(api, other_user):
    link = LinkFactory(owner=other_user)

    assert api.delete(detail(link)).status_code == 404
    assert Link.objects.filter(id=link.id).exists()


# --- update / delete ---------------------------------------------------------


def test_patch_tags_replaces_them(api, user):
    link = LinkFactory(owner=user)
    link.tags.add(TagFactory(owner=user, name="old"))

    r = api.patch(detail(link), {"tags": ["new", "Other"]}, format="json")

    assert r.status_code == 200
    assert r.json()["tags"] == ["new", "other"]


def test_patch_without_tags_keeps_existing_tags(api, user):
    link = LinkFactory(owner=user)
    link.tags.add(TagFactory(owner=user, name="keep"))

    r = api.patch(detail(link), {"url": "https://example.com/moved"}, format="json")

    assert r.status_code == 200
    assert r.json()["tags"] == ["keep"]


def test_patch_cannot_change_status(api, user):
    link = LinkFactory(owner=user)

    api.patch(detail(link), {"status": "ready"}, format="json")

    link.refresh_from_db()
    assert link.status == Link.Status.PENDING


def test_put_is_not_allowed(api, user):
    link = LinkFactory(owner=user)

    assert api.put(detail(link), {"url": "https://example.com"}, format="json").status_code == 405


def test_delete_my_link(api, user):
    link = LinkFactory(owner=user)

    assert api.delete(detail(link)).status_code == 204
    assert not Link.objects.filter(id=link.id).exists()
