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

## Menjalankan dengan Deploy Script

### Lokal (Windows)

```powershell
.\deploy-local.ps1
```

Menu interaktif:
```
[1] Jalankan dengan Docker
[2] Jalankan tanpa Docker (Python langsung)
[3] Update (git pull + rebuild Docker)
[4] Stop container
[5] Lihat logs
[6] Keluar
```

### VPS (Linux)

```bash
chmod +x deploy-vps.sh
./deploy-vps.sh
```

Menu interaktif:
```
[1] Install baru (setup Docker + build + run)
[2] Update (git pull + rebuild)
[3] Stop container
[4] Lihat logs
[5] Keluar
```

### Konfigurasi

Salin file template lalu edit:

```bash
cp .env.example .env
```

Isi `.env`:

```
AUTH_USERS=admin:password123,user1:rahasia456
SERVER_NAME=0.0.0.0
SERVER_PORT=7890
```

| Variable | Default | Keterangan |
|---|---|---|
| `AUTH_USERS` | `admin:admin` | Daftar user, format `user:pass,user2:pass2` |
| `SERVER_NAME` | `127.0.0.1` | `0.0.0.0` untuk Docker/VPS, `127.0.0.1` untuk lokal |
| `SERVER_PORT` | `7890` | Port yang digunakan |
| `MAX_SCROLL` | `30` | Maksimal iterasi scroll per halaman |
| `MAX_LINKS` | `100` | Maksimal link yang di-scrape (env menang vs slider UI) |
| `MAX_CONCURRENT` | `3` | Jumlah tab paralel per batch |
| `MAX_PAGES` | `10` | Maksimal halaman pagination |

## Menjalankan Manual

### Docker (Recommended)

```bash
docker compose up -d --build
docker compose logs -f
docker compose down
```

### Tanpa Docker (Lokal)

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

pip install -r requirements.txt
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
├── deploy-vps.sh                   # Deploy script Linux (VPS)
├── deploy-local.ps1                # Deploy script Windows (Lokal)
├── .env.example                    # Template konfigurasi auth
├── .gitignore                      # Exclude .env, __pycache__, dll
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
