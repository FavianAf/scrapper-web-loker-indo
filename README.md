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
- **Step-based error tracing** — setiap error diawali `[STEP_ID]` untuk tracing mudah
- **Proxy support** — mendukung proxy dengan autentikasi
- **Cookie persistence** — simpan/muat cookies antar sesi
- **Docker support** — siap deploy via Docker Compose

## Tech Stack

| Komponen | Teknologi |
|---|---|
| Bahasa | Python 3.11 (async) |
| Browser Automation | Playwright + Camoufox |
| Web UI | Gradio (port 7890) |
| Parsing | BeautifulSoup4, Regex |
| Deployment | Docker + Docker Compose |

## Menjalankan dengan Docker (Recommended)

```bash
# Build dan jalankan
docker compose up -d --build

# Lihat logs
docker compose logs -f

# Stop
docker compose down
```

Buka `http://localhost:7890` di browser.

### Setelah ada perubahan kode

```bash
docker compose up -d --build
```

## Menjalankan Tanpa Docker (Lokal)

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

# Jalankan
python app.py
```

Buka `http://localhost:7890` di browser.

### Menjalankan di VPS (background)

```bash
nohup python app.py > scraper.log 2>&1 &
```

## Penggunaan

1. Masukkan URL halaman direktori lowongan (contoh: `https://www.karir.com/cari?q=programmer`)
2. Atur slider: maksimal link dan halaman pagination
3. Opsional: isi Proxy URL
4. Klik **Mulai Scraping**
5. Hasil muncul bertahap di tabel
6. Export ke CSV / Excel / JSON

## Arsitektur

```
ScrappingWebLoker/
├── app.py                          # Gradio UI, handler, export
├── Dockerfile                      # Docker image definition
├── docker-compose.yml              # Docker Compose config
├── .dockerignore                   # Exclude files dari build context
├── scrapers/
│   ├── base.py                     # BaseScraper — logika utama scraping + step tracing
│   ├── scraper_karir.py            # ScraperKarir — portal karir.com
│   └── contact_extractor.py        # Ekstraksi telepon & email (regex)
├── utils/
│   ├── browser.py                  # Browser/context factory, resource blocking + step tracing
│   └── anti_block.py               # User-Agent rotation, delay, proxy config
├── tests/
│   ├── test_scraper.py             # Unit test scraper logic
│   └── test_contact_extractor.py   # Unit test contact extraction
├── requirements.txt
├── README.md
└── AGENTS.md                       # Catatan development
```

### Alur Scraping

```
User Input (URL direktori)
  │
  ├─ Launch Camoufox (fallback: Chromium)
  │
  ├─ Buka halaman direktori [SCR.10-22]
  │   ├─ Cloudflare check [SCR.13]
  │   ├─ Auto-scroll ke bawah [SCR.15]
  │   ├─ Deteksi pagination [SCR.16]
  │   ├─ Harvest link detail lowongan [SCR.17]
  │   └─ Ulangi per halaman pagination [SCR.18]
  │
  ├─ Batch processing (3 link per batch) [SCR.30-36]
  │   ├─ Buat context per batch [SCR.31]
  │   ├─ Block resource (image/css/font/media/tracking)
  │   ├─ Extract contacts (telepon + email) [SCR.40-44]
  │   ├─ Stream hasil ke UI per batch
  │   └─ Cleanup context [SCR.09]
  │
  ├─ Simpan storage state (cookies) [BRW.05]
  └─ Cleanup browser [BRW.10]
```

### Step ID Error Tracing

Setiap error di log dan kolom Error diawali `[STEP_ID]`:

| Prefix | Modul |
|---|---|
| `APP.xx` | `app.py` — UI handler, thread management |
| `SCR.xx` | `scrapers/base.py` — scraping logic |
| `BRW.xx` | `utils/browser.py` — browser lifecycle |

Contoh error di export: `[SCR.43] Timeout 30s saat goto https://...`

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
