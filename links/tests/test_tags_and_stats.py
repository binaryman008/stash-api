from links.models import Link
from links.tests.factories import LinkFactory, TagFactory


def test_tags_lists_my_tags_with_link_counts_unpaginated(api, user, other_user):
    aws = TagFactory(owner=user, name="aws")
    TagFactory(owner=user, name="empty")
    TagFactory(owner=other_user, name="not-mine")
    for _ in range(2):
        LinkFactory(owner=user).tags.add(aws)

    r = api.get("/api/tags/")

    assert r.status_code == 200
    assert [(t["name"], t["link_count"]) for t in r.json()] == [("aws", 2), ("empty", 0)]


def test_tags_is_read_only(api):
    assert api.post("/api/tags/", {"name": "new"}, format="json").status_code == 405


def test_stats_counts_only_my_links_by_status(api, user, other_user):
    LinkFactory.create_batch(2, owner=user, status=Link.Status.PENDING)
    LinkFactory.create_batch(3, owner=user, status=Link.Status.READY)
    LinkFactory(owner=user, status=Link.Status.FAILED)
    TagFactory.create_batch(2, owner=user)
    LinkFactory.create_batch(4, owner=other_user)
    TagFactory(owner=other_user)

    r = api.get("/api/stats/")

    assert r.status_code == 200
    assert r.json() == {"total": 6, "pending": 2, "ready": 3, "failed": 1, "tags": 2}


def test_stats_for_a_new_user_are_all_zero(api):
    assert api.get("/api/stats/").json() == {
        "total": 0,
        "pending": 0,
        "ready": 0,
        "failed": 0,
        "tags": 0,
    }
