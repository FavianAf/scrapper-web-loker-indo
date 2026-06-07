from __future__ import annotations

import json
import logging
import os
import tempfile
from typing import Any

from utils.anti_block import get_proxy_config

logger = logging.getLogger(__name__)

STEP: dict[str, str] = {
    "CAMOUFOX_LAUNCH": "BRW.01",
    "CHROMIUM_LAUNCH": "BRW.02",
    "PROXY_CONFIG": "BRW.03",
    "STORAGE_LOAD": "BRW.04",
    "STORAGE_SAVE": "BRW.05",
    "CTX_CREATE": "BRW.06",
    "PAGE_CREATE": "BRW.07",
    "ROUTE_SETUP": "BRW.08",
    "CTX_CLOSE": "BRW.09",
    "BROWSER_CLOSE": "BRW.10",
}


def _s(key: str) -> str:
    return f"[{STEP[key]}]"


DEFAULT_TIMEOUT: int = 30000

BROWSER_DATA_DIR = os.path.join(tempfile.gettempdir(), "loker_scraper_browser_data")
STORAGE_STATE_FILE = os.path.join(BROWSER_DATA_DIR, "storage_state.json")

BLOCKED_RESOURCE_TYPES: set[str] = {"image", "stylesheet", "font", "media"}
BLOCKED_DOMAINS: list[str] = [
    "google-analytics.com",
    "googletagmanager.com",
    "facebook.net",
    "doubleclick.net",
    "fbcdn.net",
    "adservice.google.com",
    "pagead2.googlesyndication.com",
    "amazon-adsystem.com",
    "adserver.",
    "adsrvr.org",
    "ads.yahoo.com",
    "tracking.hubspot.com",
    "mc.yandex.ru",
    "hotjar.com",
    "crazyegg.com",
    "fullstory.com",
    "log.optimizely.com",
]


async def create_browser(
    headless: bool = True,
    proxy_url: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    use_chromium: bool = False,
) -> tuple[Any, Any]:
    from playwright.async_api import async_playwright

    logger.info("%s Parse proxy config", _s("PROXY_CONFIG"))
    proxy_config = get_proxy_config(proxy_url)

    if use_chromium:
        pw = await async_playwright().start()
        launch_options: dict[str, Any] = {
            "headless": headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        }
        if proxy_config is not None:
            launch_options["proxy"] = proxy_config
        browser = await pw.chromium.launch(**launch_options)
        logger.info(
            "%s Chromium diluncurkan (headless=%s)",
            _s("CHROMIUM_LAUNCH"),
            headless,
        )
        return pw, browser

    from camoufox.async_api import AsyncCamoufox

    launch_kwargs: dict[str, Any] = {
        "headless": headless,
    }
    if proxy_config is not None:
        launch_kwargs["proxy"] = proxy_config

    camoufox_ctx = AsyncCamoufox(**launch_kwargs)
    browser = await camoufox_ctx.__aenter__()
    logger.info(
        "%s Camoufox diluncurkan (headless=%s)",
        _s("CAMOUFOX_LAUNCH"),
        headless,
    )
    if proxy_config is not None:
        logger.debug(
            "%s Proxy: %s",
            _s("PROXY_CONFIG"),
            proxy_config.get("server", "unknown"),
        )

    return camoufox_ctx, browser


async def load_storage_state(context: Any) -> None:
    if not os.path.exists(STORAGE_STATE_FILE):
        logger.info(
            "%s Storage state tidak ditemukan, fresh session",
            _s("STORAGE_LOAD"),
        )
        return
    try:
        with open(STORAGE_STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
        await context.add_cookies(state.get("cookies", []))
        logger.info("%s Storage state dimuat", _s("STORAGE_LOAD"))
    except Exception as e:
        logger.warning("%s Gagal memuat storage state: %s", _s("STORAGE_LOAD"), e)


async def save_storage_state(context: Any) -> None:
    os.makedirs(BROWSER_DATA_DIR, exist_ok=True)
    try:
        state = await context.storage_state()
        with open(STORAGE_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f)
        logger.info("%s Storage state disimpan", _s("STORAGE_SAVE"))
    except Exception as e:
        logger.warning("%s Gagal menyimpan storage state: %s", _s("STORAGE_SAVE"), e)


async def create_context(browser: Any) -> Any:
    logger.info("%s Membuat context baru", _s("CTX_CREATE"))
    context = await browser.new_context(
        viewport={"width": 1920, "height": 1080},
        locale="id-ID",
    )
    return context


async def create_page_from_context(
    context: Any,
    timeout: int = DEFAULT_TIMEOUT,
) -> Any:
    page = await context.new_page()
    page.set_default_timeout(timeout)
    page.set_default_navigation_timeout(timeout)
    await setup_resource_blocking(page)
    logger.info("%s Page + route blocking ready", _s("PAGE_CREATE"))
    return page


async def setup_resource_blocking(page: Any) -> None:
    async def handle_route(route: Any) -> None:
        if route.request.resource_type in BLOCKED_RESOURCE_TYPES:
            await route.abort()
            return
        url = route.request.url.lower()
        for domain in BLOCKED_DOMAINS:
            if domain in url:
                await route.abort()
                return
        await route.continue_()

    await page.route("**/*", handle_route)


async def close_context(context: Any) -> None:
    try:
        await context.close()
        logger.info("%s Context ditutup", _s("CTX_CLOSE"))
    except Exception as e:
        logger.error("%s Gagal menutup context: %s", _s("CTX_CLOSE"), e)


async def close_browser(pw_ctx: Any, browser: Any) -> None:
    try:
        await browser.close()
    except Exception:
        pass
    try:
        if hasattr(pw_ctx, "__aexit__"):
            await pw_ctx.__aexit__(None, None, None)
        elif hasattr(pw_ctx, "stop"):
            await pw_ctx.stop()
    except Exception:
        pass
    logger.info("%s Browser ditutup", _s("BROWSER_CLOSE"))
