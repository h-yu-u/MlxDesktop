"""Strict policy for result URLs sent to the hosted Extract service."""

import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit


class PublicResultPolicy:
    async def allowed(self, url: str) -> bool:
        try:
            parsed = urlsplit(url)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.port not in {None, 80, 443}
            ):
                return False
            addresses = await asyncio.get_running_loop().getaddrinfo(
                parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM
            )
            return bool(addresses) and all(
                ipaddress.ip_address(item[4][0]).is_global for item in addresses
            )
        except (ValueError, OSError):
            return False
