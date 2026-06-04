from __future__ import annotations

import logging
import random

logger = logging.getLogger(__name__)

USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
]

DEFAULT_DELAY_MIN: float = 1.5
DEFAULT_DELAY_MAX: float = 3.0


def get_random_user_agent() -> str:
    ua = random.choice(USER_AGENTS)
    logger.debug("User-Agent dipilih: %s", ua[:50])
    return ua


def get_random_delay(
    min_delay: float = DEFAULT_DELAY_MIN,
    max_delay: float = DEFAULT_DELAY_MAX,
) -> float:
    delay = random.uniform(min_delay, max_delay)
    logger.debug("Delay %.2f detik", delay)
    return delay


def get_proxy_config(
    proxy_url: str | None = None,
) -> dict[str, str] | None:
    if proxy_url is None:
        return None

    parsed = proxy_url
    if "@" in parsed:
        server_part = parsed.split("://")[1].split("@")[1]
        scheme = parsed.split("://")[0]
        server = f"{scheme}://{server_part}"
        username = parsed.split("://")[1].split(":")[0]
        password = parsed.split("://")[1].split(":")[1].split("@")[0]
        return {
            "server": server,
            "username": username,
            "password": password,
        }

    return {"server": proxy_url}
