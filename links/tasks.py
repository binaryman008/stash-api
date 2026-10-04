import logging

import requests
from celery import shared_task
from django.utils import timezone

from .fetching import UnsafeURLError, fetch_page
from .models import Link
from .preview import Preview, parse_preview

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def fetch_preview(self, link_id):
    link = Link.objects.filter(id=link_id).first()
    if link is None or link.status != Link.Status.PENDING:
        return  # deleted, or already processed: running twice is harmless

    try:
        page = fetch_page(link.url)
    except UnsafeURLError as exc:
        return _fail(link, str(exc))
    except requests.HTTPError as exc:
        code = exc.response.status_code
        if code >= 500 or code == 429:
            return _retry_or_fail(self, link, exc)
        return _fail(link, f"The page returned HTTP {code}.")
    except (requests.ConnectionError, requests.Timeout) as exc:
        return _retry_or_fail(self, link, exc)

    preview = parse_preview(page.html, page.url) if page.html else Preview()
    now = timezone.now()
    Link.objects.filter(id=link.id, status=Link.Status.PENDING).update(
        title=preview.title,
        description=preview.description,
        image_url=preview.image_url,
        reading_minutes=preview.reading_minutes,
        status=Link.Status.READY,
        error="",
        fetched_at=now,
        updated_at=now,
    )


def _retry_or_fail(task, link, exc):
    if task.request.retries >= task.max_retries:
        return _fail(link, "The site could not be reached.")
    logger.warning("Retrying preview for link %s: %s", link.id, exc)
    raise task.retry(exc=exc, countdown=10 * 2**task.request.retries)  # 10s, 20s, 40s


def _fail(link, reason):
    Link.objects.filter(id=link.id, status=Link.Status.PENDING).update(
        status=Link.Status.FAILED, error=reason[:255], updated_at=timezone.now()
    )