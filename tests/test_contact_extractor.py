from __future__ import annotations

from scrapers.contact_extractor import (
    extract_contacts,
    extract_emails,
    extract_phone_numbers,
)


def test_extract_phone_numbers_indonesian_format():
    text = "Hubungi kami di 081234567890 atau +6281234567890"
    result = extract_phone_numbers(text)
    assert "081234567890" in result
    assert "+6281234567890" in result


def test_extract_phone_numbers_with_spaces():
    text = "Telepon: 0812 3456 7890 untuk info lebih lanjut"
    result = extract_phone_numbers(text)
    assert len(result) == 1
    assert "081234567890" in result


def test_extract_phone_numbers_empty():
    assert extract_phone_numbers("") == []
    assert extract_phone_numbers("tidak ada nomor disini") == []


def test_extract_phone_numbers_dedup():
    text = "Nomor: 081234567890 dan 081234567890"
    result = extract_phone_numbers(text)
    assert len(result) == 1


def test_extract_phone_numbers_too_short():
    text = "Pendek: 08123"
    result = extract_phone_numbers(text)
    assert len(result) == 0


def test_extract_emails_basic():
    text = "Email: hr@company.com atau kontak@perusahaan.co.id"
    result = extract_emails(text)
    assert "hr@company.com" in result
    assert "kontak@perusahaan.co.id" in result


def test_extract_emails_case_insensitive():
    text = "Email: HR@Company.COM dan hr@company.com"
    result = extract_emails(text)
    assert len(result) == 1
    assert "hr@company.com" in result


def test_extract_emails_empty():
    assert extract_emails("") == []
    assert extract_emails("tidak ada email disini") == []


def test_extract_contacts_combined():
    text = "Hubungi 081234567890 atau email: hr@company.com"
    result = extract_contacts(text)
    assert len(result["phones"]) == 1
    assert len(result["emails"]) == 1


def test_extract_phone_numbers_62_format():
    text = "Call 6281234567890 sekarang"
    result = extract_phone_numbers(text)
    assert len(result) == 1
    assert "6281234567890" in result
