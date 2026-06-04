from __future__ import annotations

import asyncio
import logging
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

MAX_SCROLL_ITERATIONS: int = 30
STATIC_HEIGHT_THRESHOLD: int = 3
MAX_LINKS: int = 100
MAX_CONCURRENT: int = 3
MAX_PAGES: int = 10

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
        max_scroll: int = MAX_SCROLL_ITERATIONS,
        max_links: int = MAX_LINKS,
        max_pages: int = MAX_PAGES,
    ) -> None:
        self.base_url = base_url
        self.headless = headless
        self.proxy_url = proxy_url
        self.max_scroll = max_scroll
        self.max_links = max_links
        self.max_pages = max_pages
        self._pw: Any = None
        self._browser: Any = None
        self._use_chromium: bool = False

    async def _init_browser(self) -> None:
        pw, browser = await create_browser(
            headless=self.headless,
            proxy_url=self.proxy_url,
            use_chromium=self._use_chromium,
        )
        self._pw = pw
        self._browser = browser

    async def _cleanup(self) -> None:
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
                    logger.info("Scroll selesai — tinggi halaman tidak berubah")
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
                    "Cloudflare challenge resolved setelah %d detik",
                    attempt * interval,
                )
                return True

            logger.info(
                "Cloudflare challenge terdeteksi, menunggu... (%d/%d detik)",
                (attempt + 1) * interval,
                max_wait,
            )
            await asyncio.sleep(interval)

        logger.warning("Cloudflare challenge tidak resolve dalam %d detik", max_wait)
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
            logger.info("Tidak ditemukan pagination di halaman")
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

        logger.info("Ditemukan %d halaman pagination", len(pages))
        return pages

    async def _harvest_detail_links(self, page: Any) -> list[str]:
        all_hrefs = await page.evaluate("""() => {
                const anchors = Array.from(document.querySelectorAll('a[href]'));
                return anchors.map(a => a.href);
            }""")

        logger.info("Ditemukan %d tag <a> mentah di %s", len(all_hrefs), page.url)

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
            "Ditemukan %d link (%d prioritas, %d regular), diambil %d",
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
            await page.goto(url, wait_until="commit")
            await asyncio.sleep(3)

            text = await page.evaluate("document.body ? document.body.innerText : ''")
            contacts = extract_contacts(text)
            result.phones = contacts["phones"]
            result.emails = contacts["emails"]
            logger.info(
                "Halaman %s: %d telepon, %d email",
                url,
                len(result.phones),
                len(result.emails),
            )
        except PlaywrightTimeoutError:
            msg = f"Timeout saat mengakses {url}"
            logger.error(msg)
            result.error = msg
        except Exception as e:
            msg = f"Error saat mengakses {url}: {e}"
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
            await page.close()

    async def _process_batch(
        self,
        browser: Any,
        batch_links: list[str],
        cancel_event: threading.Event | None,
    ) -> list[ContactResult]:
        if cancel_event is not None and cancel_event.is_set():
            return []

        context = await create_context(browser)
        try:
            tasks = []
            for link in batch_links:
                page = await create_page_from_context(context)
                tasks.append(self._extract_and_close_page(page, link))

            try:
                results_raw = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=90,
                )
            except asyncio.TimeoutError:
                logger.warning("Batch timeout setelah 90 detik, skip batch")
                results_raw = []

            if cancel_event is not None and cancel_event.is_set():
                return []

            return [r for r in results_raw if isinstance(r, ContactResult)]
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
                results = await self._scrape_inner(
                    browser, start_url, progress_fn, cancel_event, on_batch_result
                )
            except Exception as e:
                if self._use_chromium:
                    logger.error("Chromium juga gagal: %s", e)
                    raise
                logger.warning("Camoufox crash: %s — retry dengan Chromium", e)
                await self._cleanup()
                self._use_chromium = True
                _progress(0.0, "Retry dengan Chromium...")
                await self._init_browser()
                browser = self._browser
                assert browser is not None
                results = await self._scrape_inner(
                    browser, start_url, progress_fn, cancel_event, on_batch_result
                )

        except Exception as e:
            logger.error("Fatal error saat scraping: %s", e)
        finally:
            await self._cleanup()

        return results

    async def _scrape_inner(
        self,
        browser: Any,
        start_url: str,
        progress_fn: Callable[[float, str], None] | None,
        cancel_event: threading.Event | None,
        on_batch_result: (
            Callable[[int, int, int, int, list[ContactResult]], None] | None
        ),
    ) -> list[ContactResult]:
        def _progress(pct: float, desc: str) -> None:
            if progress_fn is not None:
                progress_fn(pct, desc)

        results: list[ContactResult] = []

        listing_context = await create_context(browser)
        await load_storage_state(listing_context)
        listing_page = await listing_context.new_page()
        listing_page.set_default_timeout(DEFAULT_TIMEOUT)
        listing_page.set_default_navigation_timeout(DEFAULT_TIMEOUT)
        detail_links: list[str] = []

        try:
            _progress(0.05, f"Membuka halaman direktori: {start_url}")
            logger.info("Mengakses halaman direktori: %s", start_url)
            await listing_page.goto(start_url, wait_until="domcontentloaded")

            cf_passed = await self._wait_for_cloudflare(listing_page)
            if not cf_passed:
                logger.error("Gagal melewati Cloudflare challenge untuk %s", start_url)
                return results

            logger.info("Page title: '%s'", await listing_page.title())

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
                    logger.info("Mengakses halaman pagination: %s", pg_url)
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
                        "Halaman %d: +%d link baru (total %d)",
                        page_num,
                        len(detail_links) - before,
                        len(detail_links),
                    )

        except PlaywrightTimeoutError:
            logger.error("Timeout saat mengakses halaman direktori: %s", start_url)
        except Exception as e:
            logger.error("Error pada halaman direktori %s: %s", start_url, e)
        finally:
            await save_storage_state(listing_context)
            await listing_page.close()
            await close_context(listing_context)

        if not detail_links:
            logger.warning("Tidak ditemukan link lowongan di %s", start_url)
            _progress(1.0, "Tidak ditemukan link lowongan.")
            return results

        total = len(detail_links)
        _progress(0.12, f"Ditemukan {total} link, mulai scraping...")

        batches = [
            detail_links[i : i + MAX_CONCURRENT]
            for i in range(0, total, MAX_CONCURRENT)
        ]
        completed_count = 0

        for bi, batch_links in enumerate(batches):
            if cancel_event is not None and cancel_event.is_set():
                logger.info("Scraping dibatalkan.")
                _progress(1.0, "Scraping dibatalkan.")
                results.clear()
                return results

            try:
                batch_results = await self._process_batch(
                    browser, batch_links, cancel_event
                )
            except Exception as e:
                error_msg = str(e)
                if "Connection closed" in error_msg or (
                    "browser" in error_msg.lower() and "closed" in error_msg.lower()
                ):
                    logger.error("Browser crash saat batch %d — abort", bi + 1)
                    raise
                logger.error("Batch %d/%d error: %s — skip", bi + 1, len(batches), e)
                batch_results = []

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
        return results
