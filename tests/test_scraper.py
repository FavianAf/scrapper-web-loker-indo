from __future__ import annotations

import pytest

from scrapers.base import BaseScraper, ContactResult


def test_contact_result_defaults():
    result = ContactResult(url="https://example.com/job/1")
    assert result.url == "https://example.com/job/1"
    assert result.phones == []
    assert result.emails == []
    assert result.error is None


def test_contact_result_with_data():
    result = ContactResult(
        url="https://example.com/job/1",
        phones=["081234567890"],
        emails=["hr@example.com"],
    )
    assert len(result.phones) == 1
    assert len(result.emails) == 1


def test_scraper_init_defaults():
    scraper = BaseScraper(base_url="https://example.com")
    assert scraper.base_url == "https://example.com"
    assert scraper.headless is True
    assert scraper.proxy_url is None
    assert scraper.max_scroll == 30


def test_scraper_init_custom():
    scraper = BaseScraper(
        base_url="https://example.com",
        headless=False,
        proxy_url="http://proxy:8080",
        max_scroll=10,
    )
    assert scraper.headless is False
    assert scraper.proxy_url == "http://proxy:8080"
    assert scraper.max_scroll == 10


@pytest.mark.asyncio
async def test_scrape_returns_list():
    scraper = BaseScraper(base_url="https://invalid.test")
    results = await scraper.scrape("https://invalid.test/jobs")
    assert isinstance(results, list)


@pytest.fixture
def scraper() -> BaseScraper:
    return BaseScraper(base_url="https://www.karir.com")


def test_is_ignored_login(scraper: BaseScraper) -> None:
    assert scraper._is_ignored("https://www.karir.com/login") is True


def test_is_ignored_blog(scraper: BaseScraper) -> None:
    assert scraper._is_ignored("https://www.karir.com/blog/berita") is True


def test_is_ignored_mailto(scraper: BaseScraper) -> None:
    assert scraper._is_ignored("mailto:hr@company.com") is True


def test_is_ignored_pdf(scraper: BaseScraper) -> None:
    assert scraper._is_ignored("https://www.karir.com/document.pdf") is True


def test_is_ignored_valid_job(scraper: BaseScraper) -> None:
    assert scraper._is_ignored("https://www.karir.com/job/developer") is False


def test_is_ignored_valid_vacancy(scraper: BaseScraper) -> None:
    assert scraper._is_ignored("https://www.karir.com/vacancy/123") is False


def test_is_same_domain_match(scraper: BaseScraper) -> None:
    assert (
        scraper._is_same_domain("https://www.karir.com/job/1", "www.karir.com") is True
    )


def test_is_same_domain_mismatch(scraper: BaseScraper) -> None:
    assert (
        scraper._is_same_domain("https://www.jobstreet.co.id/job/1", "www.karir.com")
        is False
    )


def test_is_same_domain_invalid_url(scraper: BaseScraper) -> None:
    assert scraper._is_same_domain("not-a-url", "www.karir.com") is False


def test_is_pagination_page_param(scraper: BaseScraper) -> None:
    assert scraper._is_pagination("https://www.karir.com/cari?page=2") is True


def test_is_pagination_p_param(scraper: BaseScraper) -> None:
    assert scraper._is_pagination("https://www.karir.com/cari?p=3") is True


def test_is_pagination_path(scraper: BaseScraper) -> None:
    assert scraper._is_pagination("https://www.karir.com/page/2") is True


def test_is_pagination_not_pagination(scraper: BaseScraper) -> None:
    assert scraper._is_pagination("https://www.karir.com/job/developer") is False


def test_extract_page_number_query_page(scraper: BaseScraper) -> None:
    assert scraper._extract_page_number("https://www.karir.com/cari?page=3") == 3


def test_extract_page_number_query_p(scraper: BaseScraper) -> None:
    assert scraper._extract_page_number("https://www.karir.com/cari?p=5") == 5


def test_extract_page_number_path(scraper: BaseScraper) -> None:
    assert scraper._extract_page_number("https://www.karir.com/page/7") == 7


def test_extract_page_number_halaman(scraper: BaseScraper) -> None:
    assert scraper._extract_page_number("https://www.karir.com/halaman/4") == 4


def test_extract_page_number_no_page(scraper: BaseScraper) -> None:
    assert scraper._extract_page_number("https://www.karir.com/job/1") == 999
