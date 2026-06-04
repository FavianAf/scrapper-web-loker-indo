from __future__ import annotations

from scrapers.base import BaseScraper
from scrapers.contact_extractor import extract_phone_numbers, extract_emails
from scrapers.scraper_karir import ScraperKarir

__all__ = [
    "BaseScraper",
    "ScraperKarir",
    "extract_phone_numbers",
    "extract_emails",
]
