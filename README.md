# Tools Scraping Info Loker Indonesia

Tool otomatis untuk mengekstrak nomor telepon dan email dari halaman lowongan kerja di portal lowongan Indonesia.

## Fitur

- **Auto-scroll** halaman direktori untuk menemukan semua link lowongan
- **Deteksi pagination** otomatis (multi-halaman)
- **Batch processing** — 3 halaman detail per batch dengan concurrency control
- **Ekstraksi kontak** — nomor HP Indonesia (+62, 08xx) dan alamat email
- **Real-time streaming UI** — hasil muncul bertahap per batch di tabel
- **Export** ke CSV, Excel, JSON
- **Cancel** scraping kapan saja
- **Anti-detection** — Camoufox (Firefox anti-fingerprint) sebagai browser utama, Chromium sebagai fallback
- **Resource blocking** — blokir image, CSS, font, media, dan tracking domain di halaman detail untuk hemat bandwidth
- **Cloudflare detector** — deteksi dan tunggu challenge Cloudflare otomatis
- **Proxy support** — mendukung proxy dengan autentikasi
- **Cookie persistence** — simpan/muat cookies antar sesi

## Tech Stack

| Komponen | Teknologi |
|---|---|
| Bahasa | Python 3.10+ (async) |
| Browser Automation | Playwright + Camoufox |
| Web UI | Gradio (port 7890) |
| Parsing | BeautifulSoup4, Regex |

## Setup

```bash
# Buat virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Install browser binaries
playwright install chromium
python -m camoufox fetch
```

## Menjalankan

```bash
python app.py
```

Buka `http://127.0.0.1:7890` di browser.

### Menjalankan di VPS (background)

```bash
nohup python app.py > scraper.log 2>&1 &
```

## Penggunaan

1. Masukkan URL halaman direktori lowongan (contoh: `https://www.karir.com/cari?q=programmer`)
2. Atur slider: maksimal link dan halaman pagination
3. Opsional: centang Headless Mode, isi Proxy URL
4. Klik **Mulai Scraping**
5. Hasil muncul bertahap di tabel
6. Export ke CSV / Excel / JSON

## Arsitektur

```
ScrappingWebLoker/
├── app.py                          # Gradio UI, handler, export
├── scrapers/
│   ├── base.py                     # BaseScraper — logika utama scraping
│   ├── scraper_karir.py            # ScraperKarir — portal karir.com
│   └── contact_extractor.py        # Ekstraksi telepon & email (regex)
├── utils/
│   ├── browser.py                  # Browser/context factory, resource blocking
│   └── anti_block.py               # User-Agent rotation, delay, proxy config
├── tests/
│   ├── test_scraper.py             # Unit test scraper logic
│   └── test_contact_extractor.py   # Unit test contact extraction
├── requirements.txt
└── AGENTS.md                       # Catatan development
```

### Alur Scraping

```
User Input (URL direktori)
  │
  ├─ Launch Camoufox (fallback: Chromium)
  │
  ├─ Buka halaman direktori
  │   ├─ Auto-scroll ke bawah
  │   ├─ Deteksi pagination
  │   ├─ Harvest link detail lowongan
  │   └─ Ulangi per halaman pagination
  │
  ├─ Batch processing (3 link per batch)
  │   ├─ Buat context per batch
  │   ├─ Block resource (image/css/font/media/tracking)
  │   ├─ Extract contacts (telepon + email)
  │   ├─ Stream hasil ke UI per batch
  │   └─ Cleanup context
  │
  ├─ Simpan storage state (cookies)
  └─ Cleanup browser
```

## Testing

```bash
# Semua test
pytest

# File tertentu
pytest tests/test_contact_extractor.py

# Verbose
pytest -v tests/
```

## Linting & Formatting

```bash
black --check .        # Check formatting
black .                # Format semua file
ruff check .           # Lint
ruff check --fix .     # Auto-fix lint
mypy .                 # Type check
```

## Resource Disk

Browser binaries yang di-install:

| Browser | Lokasi | Ukuran |
|---|---|---|
| Camoufox | `AppData\Local\camoufox` | ~1 GB |
| Playwright Chromium | `AppData\Local\ms-playwright` | ~430 MB |
| Playwright Firefox* | `AppData\Local\ms-playwright` | ~340 MB |

*\*Tidak digunakan — bisa dihapus via `playwright uninstall firefox`*

Untuk bersihkan pip cache: `pip cache purge` (~730 MB)

## Portal yang Didukung

Secara default mendukung URL yang mengandung pattern berikut:

- `/job/`, `/loker/`, `/vacancy/`, `/lowongan/`, `/lowongan-kerja/`, `/karir/`, `/career/`, `/detail/`

Contoh URL yang valid:

- `https://www.karir.com/cari?q=programmer`
- `https://www.loker.id/lowongan-kerja/`
- `https://www.kalibrr.id/`

## Konfigurasi Proxy

Format: `http://username:password@alamatproxy:port`

Contoh: `http://admin:secret123@103.50.10.5:8080`

## Lisensi

Project ini dibuat untuk keperluan edukasi dan riset.
