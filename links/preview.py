from dataclasses import dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup

WORDS_PER_MINUTE = 200


@dataclass
class Preview:
    title: str = ""
    description: str = ""
    image_url: str = ""
    reading_minutes: int | None = None


def _meta(soup, *keys):
    for key in keys:
        tag = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
        if tag and tag.get("content", "").strip():
            return tag["content"].strip()
    return ""


def parse_preview(html: bytes, base_url: str) -> Preview:
    soup = BeautifulSoup(html, "html.parser")  # detects the encoding from the bytes
    page_title = soup.title.string.strip() if soup.title and soup.title.string else ""
    title = _meta(soup, "og:title", "twitter:title") or page_title
    description = _meta(soup, "og:description", "description", "twitter:description")

    image = _meta(soup, "og:image", "twitter:image")
    image = urljoin(base_url, image) if image else ""
    if not image.startswith(("http://", "https://")) or len(image) > 2048:
        image = ""

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    words = len(soup.get_text(" ", strip=True).split())

    return Preview(
        title=title[:500],
        description=description[:2000],
        image_url=image,
        reading_minutes=max(1, round(words / WORDS_PER_MINUTE)) if words else None,
    )