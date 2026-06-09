from __future__ import annotations

import asyncio
import logging
import os
import re
import threading
from dataclasses import dataclass, field
from typing import Any, Callable
from urllib.parse import urlparse

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from scrapers.contact_extractor import extract_contacts
from utils.anti_block import get_random_delay
from utils.browser import (
    DEFAULT_TIMEOUT,
    close_browser,
    close_context,
    create_browser,
    create_context,
    create_page_from_context,
    load_storage_state,
    save_storage_state,
)

logger = logging.getLogger(__name__)

STEP: dict[str, str] = {
    "BROWSER_INIT": "SCR.01",
    "FALLBACK": "SCR.02",
    "FATAL": "SCR.03",
    "CLEANUP": "SCR.04",
    "LISTING_CTX": "SCR.10",
    "LISTING_LOAD_STATE": "SCR.11",
    "LISTING_OPEN": "SCR.12",
    "CF_CHECK": "SCR.13",
    "CF_FAIL": "SCR.14",
    "SCROLL": "SCR.15",
    "PAGINATION": "SCR.16",
    "HARVEST": "SCR.17",
    "PAGINATION_VISIT": "SCR.18",
    "LISTING_SAVE_STATE": "SCR.19",
    "LISTING_CLOSE": "SCR.20",
    "LISTING_TIMEOUT": "SCR.21",
    "LISTING_ERROR": "SCR.22",
    "BATCH_START": "SCR.30",
    "BATCH_CTX": "SCR.31",
    "BATCH_PAGE": "SCR.32",
    "BATCH_GATHER": "SCR.33",
    "BATCH_TIMEOUT": "SCR.34",
    "BATCH_ERROR": "SCR.35",
    "BATCH_CRASH": "SCR.36",
    "DETAIL_GOTO": "SCR.40",
    "DETAIL_BODY": "SCR.41",
    "DETAIL_EXTRACT": "SCR.42",
    "DETAIL_TIMEOUT": "SCR.43",
    "DETAIL_ERROR": "SCR.44",
    "DETAIL_PAGE_CLOSE": "SCR.45",
}


def _s(key: str) -> str:
    return f"[{STEP[key]}]"


DEFAULT_MAX_SCROLL: int = 30
STATIC_HEIGHT_THRESHOLD: int = 3
DEFAULT_MAX_LINKS: int = 100
DEFAULT_MAX_CONCURRENT: int = 3
DEFAULT_MAX_PAGES: int = 10

JOB_LINK_PATTERNS: list[str] = [
    "/job/",
    "/loker/",
    "/vacancy/",
    "/lowongan/",
    "/lowongan-kerja/",
    "/karir/",
    "/career/",
    "/detail/",
]

IGNORE_PATTERNS: list[str] = [
    "/about",
    "/contact",
    "/login",
    "/register",
    "/signup",
    "/sign-in",
    "/sign-up",
    "/privacy",
    "/terms",
    "/faq",
    "/help",
    "/support",
    "/blog",
    "/news",
    "/press",
    "/careers",
    "/company/",
    "/sitemap",
    "/search",
    "/category",
    "/tag/",
    "/author/",
    "javascript:",
    "mailto:",
    "tel:",
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".css",
    ".js",
]

PAGINATION_PATTERNS: list[str] = [
    "?page=",
    "&page=",
    "?p=",
    "&p=",
    "/page/",
    "/halaman/",
    "/pages/",
]

PAGINATION_KEYWORDS: list[str] = [
    "next",
    "berikutnya",
    "selanjutnya",
    "lanjut",
    "\u00bb",
    "\u203a",
    ">>",
]


@dataclass
class ContactResult:
    url: str
    phones: list[str] = field(default_factory=list)
    emails: list[str] = field(default_factory=list)
    error: str | None = None


class BaseScraper:
    def __init__(
        self,
        base_url: str,
        headless: bool = True,
        proxy_url: str | None = None,
        max_scroll: int | None = None,
        max_links: int | None = None,
        max_pages: int | None = None,
    ) -> None:
        self.base_url = base_url
        self.headless = headless
        self.proxy_url = proxy_url
        self.max_scroll = max_scroll or int(
            os.environ.get("MAX_SCROLL", str(DEFAULT_MAX_SCROLL))
        )
        self.max_links = max_links or int(
            os.environ.get("MAX_LINKS", str(DEFAULT_MAX_LINKS))
        )
        self.max_pages = max_pages or int(
            os.environ.get("MAX_PAGES", str(DEFAULT_MAX_PAGES))
        )
        self._max_concurrent = int(
            os.environ.get("MAX_CONCURRENT", str(DEFAULT_MAX_CONCURRENT))
        )
        self._pw: Any = None
        self._browser: Any = None
        self._use_chromium: bool = False

    async def _init_browser(self) -> None:
        logger.info(
            "%s Memulai browser (chromium=%s)",
            _s("BROWSER_INIT"),
            self._use_chromium,
        )
        pw, browser = await create_browser(
            headless=self.headless,
            proxy_url=self.proxy_url,
            use_chromium=self._use_chromium,
        )
        self._pw = pw
        self._browser = browser

    async def _cleanup(self) -> None:
        logger.info("%s Cleanup browser", _s("CLEANUP"))
        if self._pw is not None and self._browser is not None:
            await close_browser(self._pw, self._browser)
            self._pw = None
            self._browser = None

    async def _scroll_to_bottom(self, page: Any) -> None:
        static_count = 0
        for _ in range(self.max_scroll):
            prev_height = await page.evaluate("document.body.scrollHeight")
            await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
            delay = get_random_delay()
            await asyncio.sleep(delay)
            new_height = await page.evaluate("document.body.scrollHeight")

            if new_height == prev_height:
                static_count += 1
                if static_count >= STATIC_HEIGHT_THRESHOLD:
                    logger.info(
                        "%s Scroll selesai — tinggi halaman tidak berubah",
                        _s("SCROLL"),
                    )
                    break
            else:
                static_count = 0

    async def _wait_for_cloudflare(
        self,
        page: Any,
        max_wait: int = 30,
        interval: int = 5,
    ) -> bool:
        cf_keywords = [
            "tunggu sebentar",
            "cloudflare",
            "verifikasi keamanan",
            "just a moment",
            "please wait",
            "checking your browser",
            "just a second",
        ]
        for attempt in range(max_wait // interval):
            try:
                title = (await page.title()).lower()
                body = (
                    await page.evaluate("document.body.innerText.substring(0, 300)")
                ).lower()
            except Exception:
                await asyncio.sleep(interval)
                continue

            is_cf = any(kw in title or kw in body for kw in cf_keywords)
            if not is_cf:
                logger.info(
                    "%s Cloudflare OK — resolved setelah %d detik",
                    _s("CF_CHECK"),
                    attempt * interval,
                )
                return True

            logger.info(
                "%s Cloudflare challenge terdeteksi (%d/%d detik)",
                _s("CF_CHECK"),
                (attempt + 1) * interval,
                max_wait,
            )
            await asyncio.sleep(interval)

        logger.warning(
            "%s Cloudflare challenge tidak resolve dalam %d detik",
            _s("CF_FAIL"),
            max_wait,
        )
        return False

    def _is_ignored(self, href: str) -> bool:
        lower = href.lower()
        for pattern in IGNORE_PATTERNS:
            if pattern in lower:
                return True
        return False

    def _is_same_domain(self, href: str, base_domain: str) -> bool:
        try:
            parsed = urlparse(href)
            return parsed.netloc == base_domain
        except Exception:
            return False

    def _is_pagination(self, href: str) -> bool:
        lower = href.lower()
        return any(p in lower for p in PAGINATION_PATTERNS)

    def _extract_page_number(self, url: str) -> int:
        match = re.search(r"[?&]page=(\d+)", url, re.IGNORECASE)
        if match:
            return int(match.group(1))
        match = re.search(r"[?&]p=(\d+)", url, re.IGNORECASE)
        if match:
            return int(match.group(1))
        match = re.search(r"/page/(\d+)", url, re.IGNORECASE)
        if match:
            return int(match.group(1))
        match = re.search(r"/halaman/(\d+)", url, re.IGNORECASE)
        if match:
            return int(match.group(1))
        match = re.search(r"/pages/(\d+)", url, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return 999

    async def _detect_pagination(self, page: Any) -> list[str]:
        current_domain = urlparse(page.url).netloc
        current_url = page.url

        pagination_data = await page.evaluate(
            """([patterns, keywords]) => {
                const anchors = Array.from(document.querySelectorAll('a[href]'));
                const results = [];
                anchors.forEach(a => {
                    const href = a.href;
                    const text = (a.textContent || '').trim().toLowerCase();
                    const lowerHref = href.toLowerCase();
                    const matchesPattern = patterns.some(p => lowerHref.includes(p));
                    const matchesKeyword = keywords.some(kw => text === kw || text.includes(kw));
                    if (matchesPattern || matchesKeyword) {
                        results.push(href);
                    }
                });
                const navElements = document.querySelectorAll(
                    'nav a[href], [class*="pagination"] a[href], [class*="pager"] a[href], [class*="paging"] a[href], [role="navigation"] a[href]'
                );
                navElements.forEach(a => {
                    const text = (a.textContent || '').trim().toLowerCase();
                    if (/^\d+$/.test(text) || keywords.some(kw => text.includes(kw))) {
                        results.push(a.href);
                    }
                });
                return results;
            }""",
            [PAGINATION_PATTERNS, PAGINATION_KEYWORDS],
        )

        if not pagination_data:
            logger.info("%s Tidak ditemukan pagination", _s("PAGINATION"))
            return []

        seen: set[str] = set()
        pages: list[str] = []

        for url in pagination_data:
            if not url or url == current_url:
                continue
            if url in seen:
                continue
            if not self._is_same_domain(url, current_domain):
                continue
            if not self._is_pagination(url):
                continue

            normalized = url.split("#")[0].rstrip("/")
            if normalized in seen:
                continue
            seen.add(normalized)
            pages.append(normalized)

        pages.sort(key=self._extract_page_number)
        pages = pages[: self.max_pages]

        logger.info(
            "%s Ditemukan %d halaman pagination",
            _s("PAGINATION"),
            len(pages),
        )
        return pages

    async def _harvest_detail_links(self, page: Any) -> list[str]:
        all_hrefs = await page.evaluate("""() => {
                const anchors = Array.from(document.querySelectorAll('a[href]'));
                return anchors.map(a => a.href);
            }""")

        logger.info(
            "%s Ditemukan %d tag <a> mentah di %s",
            _s("HARVEST"),
            len(all_hrefs),
            page.url,
        )

        current_domain = urlparse(page.url).netloc

        priority: list[str] = []
        regular: list[str] = []
        seen: set[str] = set()

        for href in all_hrefs:
            if not href or href in seen:
                continue
            if self._is_ignored(href):
                continue
            if self._is_pagination(href):
                continue
            if not self._is_same_domain(href, current_domain):
                continue

            parsed = urlparse(href)
            path = parsed.path.rstrip("/")
            if not path or path == "/":
                continue

            seen.add(href)

            is_job = any(p in href.lower() for p in JOB_LINK_PATTERNS)
            if is_job:
                priority.append(href)
            else:
                regular.append(href)

        links = (priority + regular)[: self.max_links]

        logger.info(
            "%s %d link (%d prioritas, %d regular), diambil %d",
            _s("HARVEST"),
            len(priority) + len(regular),
            len(priority),
            len(regular),
            len(links),
        )
        return links

    async def _extract_from_detail_page(
        self,
        page: Any,
        url: str,
    ) -> ContactResult:
        result = ContactResult(url=url)
        try:
            logger.info("%s goto %s", _s("DETAIL_GOTO"), url)
            await page.goto(url, wait_until="commit")
            await asyncio.sleep(3)

            logger.info("%s Extract body: %s", _s("DETAIL_BODY"), url)
            text = await page.evaluate("document.body ? document.body.innerText : ''")

            logger.info("%s Extract contacts: %s", _s("DETAIL_EXTRACT"), url)
            contacts = extract_contacts(text)
            result.phones = contacts["phones"]
            result.emails = contacts["emails"]
            logger.info(
                "%s %s: %d telepon, %d email",
                _s("DETAIL_EXTRACT"),
                url,
                len(result.phones),
                len(result.emails),
            )
        except PlaywrightTimeoutError:
            msg = f"{_s('DETAIL_TIMEOUT')} Timeout 30s saat goto {url}"
            logger.error(msg)
            result.error = msg
        except Exception as e:
            msg = f"{_s('DETAIL_ERROR')} {type(e).__name__}: {e} — pada {url}"
            logger.error(msg)
            result.error = msg
        return result

    async def _extract_and_close_page(
        self,
        page: Any,
        url: str,
    ) -> ContactResult:
        try:
            return await self._extract_from_detail_page(page, url)
        finally:
            try:
                await page.close()
            except Exception as e:
                logger.warning(
                    "%s Gagal close page %s: %s",
                    _s("DETAIL_PAGE_CLOSE"),
                    url,
                    e,
                )

    async def _process_batch(
        self,
        browser: Any,
        batch_links: list[str],
        cancel_event: threading.Event | None,
    ) -> list[ContactResult]:
        if cancel_event is not None and cancel_event.is_set():
            return []

        logger.info(
            "%s Membuat context untuk batch (%d link)",
            _s("BATCH_CTX"),
            len(batch_links),
        )
        context = await create_context(browser)
        try:
            tasks = []
            for link in batch_links:
                page = await create_page_from_context(context)
                tasks.append(self._extract_and_close_page(page, link))

            try:
                logger.info(
                    "%s gather %d task paralel",
                    _s("BATCH_GATHER"),
                    len(tasks),
                )
                results_raw = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=90,
                )
            except asyncio.TimeoutError:
                logger.warning("%s Batch timeout setelah 90 detik", _s("BATCH_TIMEOUT"))
                return [
                    ContactResult(
                        url=link,
                        error=f"{_s('BATCH_TIMEOUT')} Batch timeout 90s",
                    )
                    for link in batch_links
                ]

            if cancel_event is not None and cancel_event.is_set():
                return []

            converted: list[ContactResult] = []
            for i, r in enumerate(results_raw):
                if isinstance(r, ContactResult):
                    converted.append(r)
                elif isinstance(r, Exception):
                    url = batch_links[i] if i < len(batch_links) else "unknown"
                    logger.error(
                        "%s Exception pada link %s: %s",
                        _s("BATCH_GATHER"),
                        url,
                        r,
                    )
                    converted.append(
                        ContactResult(
                            url=url,
                            error=f"{_s('BATCH_GATHER')} {type(r).__name__}: {r}",
                        )
                    )
            return converted
        finally:
            for pg in context.pages:
                try:
                    await pg.close()
                except Exception:
                    pass
            await close_context(context)

    async def scrape(
        self,
        start_url: str,
        progress_fn: Callable[[float, str], None] | None = None,
        cancel_event: threading.Event | None = None,
        on_batch_result: (
            Callable[[int, int, int, int, list[ContactResult]], None] | None
        ) = None,
    ) -> list[ContactResult]:
        def _progress(pct: float, desc: str) -> None:
            if progress_fn is not None:
                progress_fn(pct, desc)

        results: list[ContactResult] = []
        try:
            _progress(0.0, "Memulai browser...")
            await self._init_browser()
            browser = self._browser
            assert browser is not None

            try:
                await self._scrape_inner(
                    browser,
                    start_url,
                    results,
                    progress_fn,
                    cancel_event,
                    on_batch_result,
                )
            except Exception as e:
                if self._use_chromium:
                    logger.error("%s Chromium juga gagal: %s", _s("FATAL"), e)
                    raise
                logger.warning(
                    "%s Camoufox crash: %s — retry Chromium",
                    _s("FALLBACK"),
                    e,
                )
                results.clear()
                await self._cleanup()
                self._use_chromium = True
                _progress(0.0, "Retry dengan Chromium...")
                await self._init_browser()
                browser = self._browser
                assert browser is not None
                await self._scrape_inner(
                    browser,
                    start_url,
                    results,
                    progress_fn,
                    cancel_event,
                    on_batch_result,
                )

        except Exception as e:
            logger.error("%s Fatal error: %s", _s("FATAL"), e)
            results.append(
                ContactResult(
                    url=start_url,
                    error=f"{_s('FATAL')} {type(e).__name__}: {e}",
                )
            )
        finally:
            await self._cleanup()

        return results

    async def _scrape_inner(
        self,
        browser: Any,
        start_url: str,
        results: list[ContactResult],
        progress_fn: Callable[[float, str], None] | None,
        cancel_event: threading.Event | None,
        on_batch_result: (
            Callable[[int, int, int, int, list[ContactResult]], None] | None
        ),
    ) -> None:
        def _progress(pct: float, desc: str) -> None:
            if progress_fn is not None:
                progress_fn(pct, desc)

        logger.info("%s Membuat listing context", _s("LISTING_CTX"))
        listing_context = await create_context(browser)

        logger.info("%s Load storage state", _s("LISTING_LOAD_STATE"))
        await load_storage_state(listing_context)

        listing_page = await listing_context.new_page()
        listing_page.set_default_timeout(DEFAULT_TIMEOUT)
        listing_page.set_default_navigation_timeout(DEFAULT_TIMEOUT)
        detail_links: list[str] = []

        try:
            _progress(0.05, f"Membuka halaman direktori: {start_url}")
            logger.info("%s Membuka listing: %s", _s("LISTING_OPEN"), start_url)
            await listing_page.goto(start_url, wait_until="domcontentloaded")

            logger.info("%s Cek Cloudflare", _s("CF_CHECK"))
            cf_passed = await self._wait_for_cloudflare(listing_page)
            if not cf_passed:
                logger.error("%s Cloudflare gagal untuk %s", _s("CF_FAIL"), start_url)
                results.append(
                    ContactResult(
                        url=start_url,
                        error=f"{_s('CF_FAIL')} Cloudflare challenge tidak resolve dalam 30 detik",
                    )
                )
                return

            title = await listing_page.title()
            logger.info("%s Page title: '%s'", _s("LISTING_OPEN"), title)

            _progress(0.08, "Scrolling halaman...")
            await self._scroll_to_bottom(listing_page)

            _progress(0.09, "Deteksi pagination...")
            pagination_urls = await self._detect_pagination(listing_page)

            _progress(0.10, "Mengumpulkan link halaman 1...")
            detail_links = await self._harvest_detail_links(listing_page)

            if pagination_urls:
                total_pages = len(pagination_urls) + 1
                for pi, pg_url in enumerate(pagination_urls):
                    if len(detail_links) >= self.max_links:
                        break
                    if cancel_event is not None and cancel_event.is_set():
                        break
                    page_num = pi + 2
                    _progress(
                        0.10,
                        f"Mengumpulkan link halaman {page_num}/{total_pages}...",
                    )
                    logger.info(
                        "%s Pagination halaman %d: %s",
                        _s("PAGINATION_VISIT"),
                        page_num,
                        pg_url,
                    )
                    await listing_page.goto(pg_url, wait_until="domcontentloaded")
                    await self._wait_for_cloudflare(listing_page)
                    delay = get_random_delay()
                    await asyncio.sleep(delay)
                    await self._scroll_to_bottom(listing_page)
                    page_links = await self._harvest_detail_links(listing_page)
                    before = len(detail_links)
                    for link in page_links:
                        if link not in detail_links:
                            detail_links.append(link)
                    logger.info(
                        "%s Halaman %d: +%d link baru (total %d)",
                        _s("PAGINATION_VISIT"),
                        page_num,
                        len(detail_links) - before,
                        len(detail_links),
                    )

        except PlaywrightTimeoutError:
            logger.error("%s Timeout listing: %s", _s("LISTING_TIMEOUT"), start_url)
            results.append(
                ContactResult(
                    url=start_url,
                    error=f"{_s('LISTING_TIMEOUT')} Timeout saat mengakses halaman direktori",
                )
            )
        except Exception as e:
            logger.error("%s Error listing %s: %s", _s("LISTING_ERROR"), start_url, e)
            results.append(
                ContactResult(
                    url=start_url,
                    error=f"{_s('LISTING_ERROR')} {type(e).__name__}: {e}",
                )
            )
        finally:
            logger.info("%s Save storage state", _s("LISTING_SAVE_STATE"))
            await save_storage_state(listing_context)
            logger.info("%s Close listing context", _s("LISTING_CLOSE"))
            await listing_page.close()
            await close_context(listing_context)

        if not detail_links:
            logger.warning(
                "%s Tidak ditemukan link lowongan di %s",
                _s("HARVEST"),
                start_url,
            )
            _progress(1.0, "Tidak ditemukan link lowongan.")
            return

        total = len(detail_links)
        _progress(0.12, f"Ditemukan {total} link, mulai scraping...")

        batches = [
            detail_links[i : i + self._max_concurrent]
            for i in range(0, total, self._max_concurrent)
        ]
        completed_count = 0

        for bi, batch_links in enumerate(batches):
            if cancel_event is not None and cancel_event.is_set():
                logger.info("%s Scraping dibatalkan", _s("BATCH_START"))
                _progress(1.0, "Scraping dibatalkan.")
                results.clear()
                return

            try:
                logger.info(
                    "%s Batch %d/%d start",
                    _s("BATCH_START"),
                    bi + 1,
                    len(batches),
                )
                batch_results = await self._process_batch(
                    browser, batch_links, cancel_event
                )
            except Exception as e:
                error_msg = str(e)
                is_crash = "Connection closed" in error_msg or (
                    "browser" in error_msg.lower() and "closed" in error_msg.lower()
                )
                if is_crash:
                    logger.error(
                        "%s Browser crash saat batch %d — abort",
                        _s("BATCH_CRASH"),
                        bi + 1,
                    )
                    for remaining_batch in batches[bi + 1 :]:
                        for link in remaining_batch:
                            results.append(
                                ContactResult(
                                    url=link,
                                    error=f"{_s('BATCH_CRASH')} Browser crash — link tidak terproses",
                                )
                            )
                    raise
                logger.error(
                    "%s Batch %d/%d error: %s",
                    _s("BATCH_ERROR"),
                    bi + 1,
                    len(batches),
                    e,
                )
                batch_results = [
                    ContactResult(
                        url=link,
                        error=f"{_s('BATCH_ERROR')} {type(e).__name__}: {e}",
                    )
                    for link in batch_links
                ]

            results.extend(batch_results)
            completed_count += len(batch_links)

            _progress(
                0.12 + 0.88 * (completed_count / total),
                f"Scraping {completed_count}/{total}...",
            )

            if on_batch_result is not None and batch_results:
                on_batch_result(
                    bi + 1, len(batches), completed_count, total, batch_results
                )

        _progress(1.0, f"Selesai! {len(results)} halaman diproses.")
