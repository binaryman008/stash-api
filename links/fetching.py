import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import requests

MAX_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 5
TIMEOUT = (3.05, 10)  # (connect, read) seconds
USER_AGENT = "StashBot/0.1 (+https://github.com/binaryman008/stash-api)"


class UnsafeURLError(ValueError):
    """The URL points somewhere we must never fetch. Permanent, never retried."""


@dataclass
class Page:
    url: str  # final URL after redirects
    html: bytes | None  # None when the response isn't HTML (a PDF, an image…)


def assert_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise UnsafeURLError("Only http and https URLs can be saved.")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeURLError(f"Could not resolve {parsed.hostname}.") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if ip.version == 6 and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        if not ip.is_global:
            raise UnsafeURLError(f"{parsed.hostname} points to a private address.")


def fetch_page(url: str) -> Page:
    for _ in range(MAX_REDIRECTS + 1):
        assert_public_url(url)
        resp = requests.get(
            url,
            timeout=TIMEOUT,
            allow_redirects=False,  # follow redirects ourselves so every hop is checked
            stream=True,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
        )
        with resp:
            if resp.is_redirect:
                url = urljoin(url, resp.headers["Location"])
                continue
            resp.raise_for_status()
            if "html" not in resp.headers.get("Content-Type", ""):
                return Page(url=url, html=None)
            body = bytearray()
            for chunk in resp.iter_content(64 * 1024):
                body += chunk
                if len(body) >= MAX_BYTES:
                    break  # the <head> is at the top; the first 2 MB is plenty
            return Page(url=url, html=bytes(body))
    raise UnsafeURLError("Too many redirects.")