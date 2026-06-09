$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ComposeFile = Join-Path $ScriptDir "docker-compose.yml"
$EnvFile = Join-Path $ScriptDir ".env"
$EnvExample = Join-Path $ScriptDir ".env.example"
$VenvDir = Join-Path $ScriptDir "venv"

function Print-Header {
    Write-Host ""
    Write-Host "=== Loker Scraper Deploy (Lokal) ===" -ForegroundColor Cyan
    Write-Host ""
}

function Print-MainMenu {
    Write-Host "Pilih mode:" -ForegroundColor White
    Write-Host "  [1] Docker" -ForegroundColor Green
    Write-Host "  [2] Tanpa Docker" -ForegroundColor Green
    Write-Host "  [3] Bersihkan Cache & Log" -ForegroundColor Green
    Write-Host "  [4] Keluar" -ForegroundColor Green
    Write-Host ""
}

function Print-DockerMenu {
    Write-Host ""
    Write-Host "--- Docker ---" -ForegroundColor Cyan
    Write-Host "  [1] Setup & Jalankan (build image + run)" -ForegroundColor Green
    Write-Host "  [2] Update (git pull + rebuild)" -ForegroundColor Green
    Write-Host "  [3] Stop container" -ForegroundColor Green
    Write-Host "  [4] Lihat logs" -ForegroundColor Green
    Write-Host "  [5] Kembali" -ForegroundColor Yellow
    Write-Host ""
}

function Print-PythonMenu {
    Write-Host ""
    Write-Host "--- Tanpa Docker ---" -ForegroundColor Cyan
    Write-Host "  [1] Setup & Jalankan (install deps + run)" -ForegroundColor Green
    Write-Host "  [2] Jalankan saja" -ForegroundColor Green
    Write-Host "  [3] Update (git pull)" -ForegroundColor Green
    Write-Host "  [4] Kembali" -ForegroundColor Yellow
    Write-Host ""
}

function Print-CleanupMenu {
    Write-Host ""
    Write-Host "--- Bersihkan Cache & Log ---" -ForegroundColor Cyan
    Write-Host "  [1] Bersihkan semua" -ForegroundColor Green
    Write-Host "  [2] Bersihkan Python cache saja (__pycache__, .pytest_cache, .ruff_cache, *.pyc)" -ForegroundColor Green
    Write-Host "  [3] Bersihkan Log saja (*.log)" -ForegroundColor Green
    Write-Host "  [4] Bersihkan Browser temp data (cookies, leaked profiles)" -ForegroundColor Green
    Write-Host "  [5] Bersihkan pip cache" -ForegroundColor Green
    Write-Host "  [6] Bersihkan Docker cache (build cache + unused images)" -ForegroundColor Green
    Write-Host "  [7] Kembali" -ForegroundColor Yellow
    Write-Host ""
}

function Test-DockerRunning {
    try {
        $null = docker info 2>&1
        return $true
    }
    catch {
        return $false
    }
}

function Setup-Env {
    if (-not (Test-Path $EnvFile)) {
        if (Test-Path $EnvExample) {
            Copy-Item $EnvExample $EnvFile
            Write-Host "File .env dibuat dari .env.example" -ForegroundColor Yellow
            Write-Host "Edit password sebelum melanjutkan:" -ForegroundColor Yellow
            Write-Host "  notepad $EnvFile" -ForegroundColor White
            Write-Host ""
            $confirm = Read-Host "Sudah edit .env? (y/n)"
            if ($confirm -ne "y" -and $confirm -ne "Y") {
                Write-Host "Edit .env terlebih dahulu, lalu jalankan script ini lagi."
                return $false
            }
        }
        else {
            "AUTH_USERS=admin:admin" | Out-File -FilePath $EnvFile -Encoding utf8
            Write-Host "File .env dibuat dengan default (admin:admin). Silakan edit." -ForegroundColor Yellow
        }
    }
    return $true
}

function Ensure-Docker {
    if (Test-DockerRunning) {
        return $true
    }

    Write-Host "Docker Desktop tidak berjalan." -ForegroundColor Red
    $start = Read-Host "Start Docker Desktop sekarang? (y/n)"
    if ($start -ne "y" -and $start -ne "Y") {
        return $false
    }

    $dockerPath = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (-not (Test-Path $dockerPath)) {
        Write-Host "Docker Desktop tidak ditemukan. Install dari https://docker.com" -ForegroundColor Red
        return $false
    }

    Start-Process $dockerPath
    Write-Host "Menunggu Docker Desktop start..." -ForegroundColor Yellow
    $timeout = 60
    $elapsed = 0
    while ($elapsed -lt $timeout) {
        Start-Sleep -Seconds 5
        $elapsed += 5
        Write-Host "  Menunggu... ($elapsed/$timeout detik)"
        if (Test-DockerRunning) {
            return $true
        }
    }

    Write-Host "Docker gagal start. Coba manual lalu jalankan script ini lagi." -ForegroundColor Red
    return $false
}

function Docker-Setup {
    Write-Host "Setup & Jalankan Docker..." -ForegroundColor Cyan

    if (-not (Ensure-Docker)) { return }
    if (-not (Setup-Env)) { return }

    Write-Host "Building Docker image... (ini memakan waktu 5-15 menit)" -ForegroundColor Yellow
    docker compose -f $ComposeFile up -d --build

    Write-Host ""
    Write-Host "Berhasil! Scraper berjalan." -ForegroundColor Green
    Write-Host "Akses: http://localhost:7890" -ForegroundColor Cyan
    Write-Host "Login: cek file .env" -ForegroundColor White
    Write-Host ""
}

function Docker-Update {
    Write-Host "Update (Docker)..." -ForegroundColor Cyan

    if (-not (Ensure-Docker)) { return }

    Write-Host "Pulling perubahan terbaru..." -ForegroundColor Yellow
    git -C $ScriptDir pull

    Write-Host "Rebuilding..." -ForegroundColor Yellow
    docker compose -f $ComposeFile up -d --build

    Write-Host ""
    Write-Host "Update selesai!" -ForegroundColor Green
    Write-Host "Akses: http://localhost:7890" -ForegroundColor Cyan
    Write-Host ""
}

function Docker-Stop {
    Write-Host "Stop container..." -ForegroundColor Cyan
    docker compose -f $ComposeFile down
    Write-Host "Container dihentikan." -ForegroundColor Green
    Write-Host ""
}

function Docker-Logs {
    Write-Host "--- Logs (Ctrl+C untuk keluar) ---" -ForegroundColor Cyan
    docker compose -f $ComposeFile logs -f
}

function Test-VenvReady {
    $pipPath = Join-Path $VenvDir "Scripts\pip.exe"
    return Test-Path $pipPath
}

function Test-DepsInstalled {
    $pipPath = Join-Path $VenvDir "Scripts\pip.exe"
    $result = & $pipPath check 2>&1
    if ($LASTEXITCODE -eq 0) {
        return $true
    }
    return $false
}

function Test-PlaywrightInstalled {
    $chromiumDir = Join-Path $env:LOCALAPPDATA "ms-playwright"
    if (-not (Test-Path $chromiumDir)) {
        return $false
    }
    $dirs = Get-ChildItem $chromiumDir -Directory | Where-Object { $_.Name -match "^chromium" }
    return ($dirs.Count -gt 0)
}

function Test-CamoufoxInstalled {
    $camoufoxDir = Join-Path $env:LOCALAPPDATA "camoufox"
    return Test-Path $camoufoxDir
}

function Python-Setup {
    Write-Host "Setup & Jalankan (Tanpa Docker)..." -ForegroundColor Cyan

    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) {
        Write-Host "Python tidak ditemukan. Install dari https://python.org" -ForegroundColor Red
        return
    }

    if (-not (Setup-Env)) { return }

    if (-not (Test-VenvReady)) {
        Write-Host "Membuat virtual environment..." -ForegroundColor Yellow
        python -m venv $VenvDir
    }

    if (-not (Test-DepsInstalled)) {
        Write-Host "Installing dependencies..." -ForegroundColor Yellow
        $pipPath = Join-Path $VenvDir "Scripts\pip.exe"
        & $pipPath install -r (Join-Path $ScriptDir "requirements.txt")
    }
    else {
        Write-Host "Dependencies sudah terinstall, skip." -ForegroundColor Green
    }

    if (-not (Test-PlaywrightInstalled)) {
        Write-Host "Installing Playwright Chromium..." -ForegroundColor Yellow
        $pwPath = Join-Path $VenvDir "Scripts\playwright.exe"
        & $pwPath install chromium
    }
    else {
        Write-Host "Playwright Chromium sudah ada, skip." -ForegroundColor Green
    }

    if (-not (Test-CamoufoxInstalled)) {
        Write-Host "Downloading Camoufox binary..." -ForegroundColor Yellow
        $pyPath = Join-Path $VenvDir "Scripts\python.exe"
        & $pyPath -m camoufox fetch
    }
    else {
        Write-Host "Camoufox binary sudah ada, skip." -ForegroundColor Green
    }

    Write-Host ""
    Write-Host "Menjalankan app.py..." -ForegroundColor Green
    Write-Host "Akses: http://localhost:7890" -ForegroundColor Cyan
    Write-Host "Tekan Ctrl+C untuk berhenti." -ForegroundColor Yellow
    Write-Host ""

    $pyExe = Join-Path $VenvDir "Scripts\python.exe"
    & $pyExe (Join-Path $ScriptDir "app.py")
}

function Python-Run {
    Write-Host "Jalankan saja (Tanpa Docker)..." -ForegroundColor Cyan

    if (-not (Test-VenvReady)) {
        Write-Host "Virtual environment tidak ditemukan. Jalankan Setup & Jalankan dulu (opsi 1)." -ForegroundColor Red
        return
    }

    Write-Host "Menjalankan app.py..." -ForegroundColor Green
    Write-Host "Akses: http://localhost:7890" -ForegroundColor Cyan
    Write-Host "Tekan Ctrl+C untuk berhenti." -ForegroundColor Yellow
    Write-Host ""

    $pyExe = Join-Path $VenvDir "Scripts\python.exe"
    & $pyExe (Join-Path $ScriptDir "app.py")
}

function Python-Update {
    Write-Host "Update (Tanpa Docker)..." -ForegroundColor Cyan
    git -C $ScriptDir pull
    Write-Host ""
    Write-Host "Update selesai! Jalankan dengan opsi [2]." -ForegroundColor Green
    Write-Host ""
}

function Cleanup-PythonCache {
    Write-Host "Membersihkan Python cache..." -ForegroundColor Yellow

    $dirs = Get-ChildItem -Path $ScriptDir -Recurse -Directory -Include "__pycache__",".pytest_cache",".ruff_cache" -ErrorAction SilentlyContinue
    $count = 0
    foreach ($d in $dirs) {
        Remove-Item $d.FullName -Recurse -Force
        $count++
    }

    $files = Get-ChildItem -Path $ScriptDir -Recurse -File -Include "*.pyc","*.pyo" -ErrorAction SilentlyContinue
    foreach ($f in $files) {
        Remove-Item $f.FullName -Force
        $count++
    }

    Write-Host "  Dihapus: $count item" -ForegroundColor Green
}

function Cleanup-Logs {
    Write-Host "Membersihkan file log..." -ForegroundColor Yellow

    $files = Get-ChildItem -Path $ScriptDir -Recurse -File -Include "*.log" -ErrorAction SilentlyContinue
    $count = 0
    foreach ($f in $files) {
        Remove-Item $f.FullName -Force
        $count++
    }

    Write-Host "  Dihapus: $count file log" -ForegroundColor Green
}

function Cleanup-BrowserTemp {
    Write-Host "Membersihkan browser temp data..." -ForegroundColor Yellow

    $tempDir = $env:TEMP
    $count = 0

    $browserDataDir = Join-Path $tempDir "loker_scraper_browser_data"
    if (Test-Path $browserDataDir) {
        Remove-Item $browserDataDir -Recurse -Force
        Write-Host "  Dihapus: loker_scraper_browser_data" -ForegroundColor Green
        $count++
    }

    $leakedProfiles = Get-ChildItem -Path $tempDir -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -match "^playwright.*profile" }
    foreach ($p in $leakedProfiles) {
        Remove-Item $p.FullName -Recurse -Force
        $count++
    }

    $leakedExports = Get-ChildItem -Path $tempDir -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -match "^tmp.*\.(csv|xlsx|json)$" }
    foreach ($e in $leakedExports) {
        Remove-Item $e.FullName -Force
        $count++
    }

    Write-Host "  Dihapus: $count item" -ForegroundColor Green
}

function Cleanup-PipCache {
    Write-Host "Membersihkan pip cache..." -ForegroundColor Yellow
    python -m pip cache purge 2>$null
    Write-Host "  Pip cache dibersihkan." -ForegroundColor Green
}

function Cleanup-DockerCache {
    Write-Host "Membersihkan Docker cache..." -ForegroundColor Yellow

    if (-not (Test-DockerRunning)) {
        Write-Host "  Docker tidak berjalan, skip." -ForegroundColor Red
        return
    }

    docker system prune -af 2>$null
    docker builder prune -af 2>$null
    Write-Host "  Docker cache dibersihkan." -ForegroundColor Green
}

function Cleanup-All {
    Write-Host "Membersihkan semua..." -ForegroundColor Cyan
    Cleanup-PythonCache
    Cleanup-Logs
    Cleanup-BrowserTemp
    Cleanup-PipCache
    Cleanup-DockerCache
    Write-Host ""
    Write-Host "Selesai! Semua cache dan log dibersihkan." -ForegroundColor Green
    Write-Host ""
}

function Main {
    Print-Header

    while ($true) {
        Print-MainMenu
        $mode = Read-Host "Pilihan"

        switch ($mode) {
            "1" {
                while ($true) {
                    Print-DockerMenu
                    $choice = Read-Host "Pilihan"
                    switch ($choice) {
                        "1" { Docker-Setup }
                        "2" { Docker-Update }
                        "3" { Docker-Stop }
                        "4" { Docker-Logs }
                        "5" { break }
                        default { Write-Host "Pilihan tidak valid." -ForegroundColor Red }
                    }
                    if ($choice -eq "5") { break }
                }
            }
            "2" {
                while ($true) {
                    Print-PythonMenu
                    $choice = Read-Host "Pilihan"
                    switch ($choice) {
                        "1" { Python-Setup }
                        "2" { Python-Run }
                        "3" { Python-Update }
                        "4" { break }
                        default { Write-Host "Pilihan tidak valid." -ForegroundColor Red }
                    }
                    if ($choice -eq "4") { break }
                }
            }
            "3" {
                while ($true) {
                    Print-CleanupMenu
                    $choice = Read-Host "Pilihan"
                    switch ($choice) {
                        "1" { Cleanup-All }
                        "2" { Cleanup-PythonCache; Write-Host "" }
                        "3" { Cleanup-Logs; Write-Host "" }
                        "4" { Cleanup-BrowserTemp; Write-Host "" }
                        "5" { Cleanup-PipCache; Write-Host "" }
                        "6" { Cleanup-DockerCache; Write-Host "" }
                        "7" { break }
                        default { Write-Host "Pilihan tidak valid." -ForegroundColor Red }
                    }
                    if ($choice -eq "7") { break }
                }
            }
            "4" {
                Write-Host "Sampai jumpa!" -ForegroundColor Green
                exit 0
            }
            default {
                Write-Host "Pilihan tidak valid." -ForegroundColor Red
            }
        }
    }
}

Main
