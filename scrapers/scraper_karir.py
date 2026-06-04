from __future__ import annotations

import logging

from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class ScraperKarir(BaseScraper):
    def __init__(
        self,
        headless: bool = True,
        proxy_url: str | None = None,
        max_scroll: int = 30,
        max_links: int = 100,
        max_pages: int = 10,
    ) -> None:
        super().__init__(
            base_url="https://www.karir.com",
            headless=headless,
            proxy_url=proxy_url,
            max_scroll=max_scroll,
            max_links=max_links,
            max_pages=max_pages,
        )
        logger.info("ScraperKarir diinisialisasi")

    async def scrape_search(self, keyword: str) -> list:
        search_url = f"{self.base_url}/cari?q={keyword}"
        logger.info("Mencari lowongan dengan keyword: %s", keyword)
        return await self.scrape(search_url)
