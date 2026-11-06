"""Outbound destinations are configured, never chosen by a model or a request (spec C.6; SEC-16).

The app makes few outbound calls: the customer systems, the model provider through its SDK, and the identity
provider. All of those URLs come from settings. `check_url` is the gate for anything else that might ever take a URL
(Milestone 11's callbacks must use it): only http or https, no credentials in the URL, an allowed host, and no
internal or metadata address unless that exact host is configured. Redirects stay off on these clients.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable, Iterable
from urllib.parse import urlsplit

METADATA_HOSTS = {"metadata.google.internal", "metadata", "instance-data"}
Resolve = Callable[[str], list[str]]


class BlockedUrl(Exception):
    pass


def _resolve(host: str) -> list[str]:
    try:
        return [str(info[4][0]) for info in socket.getaddrinfo(host, None)]
    except OSError as exc:
        raise BlockedUrl("the host doesn't resolve") from exc


def _is_internal(address: str) -> bool:
    ip = ipaddress.ip_address(address.split("%")[0])
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified


def check_url(url: str, allowed: Iterable[str]) -> str:
    """Returns the URL if it may be called. `allowed` holds configured base URLs: only their hosts pass, and only
    those hosts may be internal (a local Keycloak or the mock API). Everything else is refused, including by what its
    name resolves to."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise BlockedUrl(f"scheme '{parts.scheme}' isn't allowed")
    if parts.username or parts.password:
        raise BlockedUrl("credentials in a URL aren't allowed")
    host = (parts.hostname or "").lower()
    if not host:
        raise BlockedUrl("the URL has no host")
    hosts = {(urlsplit(base).hostname or "").lower() for base in allowed}
    if host not in hosts:
        raise BlockedUrl(f"'{host}' isn't a configured destination")
    return url


def check_external_url(url: str, allowed_hosts: Iterable[str], resolve: Resolve = _resolve) -> str:
    """For a URL that came from outside: it must be on the list and must not lead inside, by name or by address."""
    parts = urlsplit(url)
    if parts.scheme != "https":
        raise BlockedUrl("only https is allowed")
    if parts.username or parts.password:
        raise BlockedUrl("credentials in a URL aren't allowed")
    host = (parts.hostname or "").lower()
    if host in METADATA_HOSTS or host not in {h.lower() for h in allowed_hosts}:
        raise BlockedUrl(f"'{host}' isn't an allowed destination")
    for address in resolve(host):
        if _is_internal(address):
            raise BlockedUrl("that name leads to an internal address")
    return url
