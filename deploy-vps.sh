#!/usr/bin/env bash
set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
COMPOSE_FILE="$REPO_DIR/docker-compose.yml"
ENV_FILE="$REPO_DIR/.env"
ENV_EXAMPLE="$REPO_DIR/.env.example"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

print_header() {
    echo ""
    echo -e "${CYAN}=== Loker Scraper Deploy (VPS) ===${NC}"
    echo ""
}

print_menu() {
    echo -e "Pilih aksi:"
    echo -e "  ${GREEN}[1]${NC} Install baru (setup Docker + build + run)"
    echo -e "  ${GREEN}[2]${NC} Update (git pull + rebuild)"
    echo -e "  ${GREEN}[3]${NC} Stop container"
    echo -e "  ${GREEN}[4]${NC} Bersihkan Cache & Log"
    echo -e "  ${GREEN}[5]${NC} Lihat logs"
    echo -e "  ${GREEN}[6]${NC} Keluar"
    echo ""
}

print_cleanup_menu() {
    echo ""
    echo -e "${CYAN}--- Bersihkan Cache & Log ---${NC}"
    echo -e "  ${GREEN}[1]${NC} Bersihkan semua"
    echo -e "  ${GREEN}[2]${NC} Bersihkan Python cache saja (__pycache__, .pytest_cache, .ruff_cache, *.pyc)"
    echo -e "  ${GREEN}[3]${NC} Bersihkan Log saja (*.log)"
    echo -e "  ${GREEN}[4]${NC} Bersihkan Docker cache (build cache + unused images)"
    echo -e "  ${GREEN}[5]${NC} Kembali"
    echo ""
}

check_docker() {
    if command -v docker &>/dev/null; then
        return 0
    fi
    return 1
}

install_docker() {
    echo -e "${YELLOW}Docker belum terinstall. Menginstall...${NC}"

    sudo apt-get update -y
    sudo apt-get install -y \
        ca-certificates \
        curl \
        gnupg \
        lsb-release

    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
        sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg 2>/dev/null || true
    sudo chmod a+r /etc/apt/keyrings/docker.gpg

    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
        $(lsb_release -cs) stable" | \
        sudo tee /etc/apt/sources.list.d/docker.list >/dev/null

    sudo apt-get update -y
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    sudo systemctl enable docker
    sudo systemctl start docker

    if [ "$(id -u)" -ne 0 ]; then
        echo -e "${YELLOW}Menambahkan user ke group docker...${NC}"
        sudo usermod -aG docker "$USER"
        echo -e "${YELLOW}Silakan logout lalu login lagi, lalu jalankan script ini kembali.${NC}"
        exit 0
    fi

    echo -e "${GREEN}Docker berhasil diinstall.${NC}"
}

setup_env() {
    if [ ! -f "$ENV_FILE" ]; then
        if [ -f "$ENV_EXAMPLE" ]; then
            cp "$ENV_EXAMPLE" "$ENV_FILE"
            echo -e "${YELLOW}File .env dibuat dari .env.example${NC}"
            echo -e "${YELLOW}Edit password sebelum melanjutkan:${NC}"
            echo -e "  nano $ENV_FILE"
            echo ""
            read -p "Sudah edit .env? (y/n): " confirm
            if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
                echo "Edit .env terlebih dahulu, lalu jalankan script ini lagi."
                exit 0
            fi
        else
            echo "AUTH_USERS=admin:admin" > "$ENV_FILE"
            echo -e "${YELLOW}File .env dibuat dengan default (admin:admin). Silakan edit.${NC}"
        fi
    fi
}

get_server_ip() {
    curl -s ifconfig.me 2>/dev/null || \
    curl -s icanhazip.com 2>/dev/null || \
    echo "IP_SERVER"
}

action_install() {
    echo -e "${CYAN}--- Install Baru ---${NC}"

    if ! check_docker; then
        install_docker
    fi

    setup_env

    echo -e "${YELLOW}Building Docker image... (ini memakan waktu 5-15 menit)${NC}"
    docker compose -f "$COMPOSE_FILE" up -d --build

    echo ""
    echo -e "${GREEN}Berhasil! Scraper berjalan.${NC}"
    echo -e "Akses: ${CYAN}http://$(get_server_ip):7890${NC}"
    echo -e "Login: cek file .env"
    echo ""
}

action_update() {
    echo -e "${CYAN}--- Update ---${NC}"

    if ! check_docker; then
        echo -e "${RED}Docker belum terinstall. Jalankan opsi [1] terlebih dahulu.${NC}"
        return
    fi

    echo -e "${YELLOW}Pulling perubahan terbaru...${NC}"
    git -C "$REPO_DIR" pull

    echo -e "${YELLOW}Rebuilding...${NC}"
    docker compose -f "$COMPOSE_FILE" up -d --build

    echo ""
    echo -e "${GREEN}Update selesai!${NC}"
    echo -e "Akses: ${CYAN}http://$(get_server_ip):7890${NC}"
    echo ""
}

action_stop() {
    echo -e "${CYAN}--- Stop Container ---${NC}"
    docker compose -f "$COMPOSE_FILE" down
    echo -e "${GREEN}Container dihentikan.${NC}"
    echo ""
}

action_logs() {
    echo -e "${CYAN}--- Logs (Ctrl+C untuk keluar) ---${NC}"
    docker compose -f "$COMPOSE_FILE" logs -f
}

cleanup_python_cache() {
    echo -e "${YELLOW}Membersihkan Python cache...${NC}"
    count=0

    while IFS= read -r -d '' dir; do
        rm -rf "$dir"
        ((count++))
    done < <(find "$REPO_DIR" -type d \( -name "__pycache__" -o -name ".pytest_cache" -o -name ".ruff_cache" \) -print0 2>/dev/null)

    while IFS= read -r -d '' file; do
        rm -f "$file"
        ((count++))
    done < <(find "$REPO_DIR" -type f \( -name "*.pyc" -o -name "*.pyo" \) -print0 2>/dev/null)

    echo -e "  ${GREEN}Dihapus: $count item${NC}"
}

cleanup_logs() {
    echo -e "${YELLOW}Membersihkan file log...${NC}"
    count=0

    while IFS= read -r -d '' file; do
        rm -f "$file"
        ((count++))
    done < <(find "$REPO_DIR" -type f -name "*.log" -print0 2>/dev/null)

    echo -e "  ${GREEN}Dihapus: $count file log${NC}"
}

cleanup_docker_cache() {
    echo -e "${YELLOW}Membersihkan Docker cache...${NC}"

    if ! check_docker; then
        echo -e "  ${RED}Docker tidak terinstall, skip.${NC}"
        return
    fi

    docker system prune -af 2>/dev/null || true
    docker builder prune -af 2>/dev/null || true
    echo -e "  ${GREEN}Docker cache dibersihkan.${NC}"
}

cleanup_all() {
    echo -e "${CYAN}Membersihkan semua...${NC}"
    cleanup_python_cache
    cleanup_logs
    cleanup_docker_cache
    echo ""
    echo -e "${GREEN}Selesai! Semua cache dan log dibersihkan.${NC}"
    echo ""
}

action_cleanup() {
    while true; do
        print_cleanup_menu
        read -p "Pilihan: " choice
        case "$choice" in
            1) cleanup_all ;;
            2) cleanup_python_cache; echo "" ;;
            3) cleanup_logs; echo "" ;;
            4) cleanup_docker_cache; echo "" ;;
            5) return ;;
            *) echo -e "${RED}Pilihan tidak valid.${NC}" ;;
        esac
    done
}

main() {
    print_header

    while true; do
        print_menu
        read -p "Pilihan: " choice
        case "$choice" in
            1) action_install ;;
            2) action_update ;;
            3) action_stop ;;
            4) action_cleanup ;;
            5) action_logs ;;
            6) echo -e "${GREEN}Sampai jumpa!${NC}"; exit 0 ;;
            *) echo -e "${RED}Pilihan tidak valid.${NC}" ;;
        esac
    done
}

main
