#!/usr/bin/env bash
# deploy/edge/install.sh — установка edge-сервера публичного сайта на чистом
# Debian-хосте (Москва, W26). Идемпотентен: повторный запуск обновляет код и
# пересобирает фронтенд, не ломая уже настроенное.
#
# Что делает:
#   1. ставит системные пакеты и Caddy (официальный apt-репозиторий);
#   2. ставит Node 20 LTS, если подходящего Node нет (NodeSource);
#   3. создаёт venv и ставит Python-зависимости;
#   4. собирает фронтенд: npm ci && npm run build -> frontend/dist;
#   5. создаёт каталог снапшота и .env (из deploy/edge/edge.env.example);
#   6. ставит Caddyfile и systemd-юнит, перезагружает Caddy, включает сервис.
#
# Использование:
#   sudo bash deploy/edge/install.sh
#   sudo EDGE_DOMAIN=raspisanie.example.ru bash deploy/edge/install.sh
#
# Переопределяемые переменные (env):
#   EDGE_DOMAIN   домен .ru для Caddy (по умолчанию schedule.example.ru)
#   EDGE_PORT     порт приложения (по умолчанию 8090)
#   EDGE_USER     пользователь сервиса (по умолчанию raspisanie)
#   EDGE_DIR      каталог приложения (по умолчанию — корень репозитория)
#   EDGE_ENV_FILE файл окружения сервиса (по умолчанию /etc/raspisanie-edge.env)
#   EDGE_SNAPSHOT_DIR каталог снапшота (по умолчанию /var/lib/raspisanie-edge)
set -Eeuo pipefail

# --- Пути и параметры ----------------------------------------------------------
deploy_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${deploy_dir}/../.." && pwd)"

EDGE_DOMAIN="${EDGE_DOMAIN:-schedule.example.ru}"
EDGE_PORT="${EDGE_PORT:-8090}"
EDGE_USER="${EDGE_USER:-raspisanie}"
EDGE_DIR="${EDGE_DIR:-$repo_root}"
EDGE_ENV_FILE="${EDGE_ENV_FILE:-/etc/raspisanie-edge.env}"
EDGE_SNAPSHOT_DIR="${EDGE_SNAPSHOT_DIR:-/var/lib/raspisanie-edge}"

VENV_DIR="${EDGE_DIR}/.venv"
FRONTEND_DIR="${EDGE_DIR}/frontend"
DIST_DIR="${FRONTEND_DIR}/dist"
CADDYFILE_SRC="${deploy_dir}/Caddyfile"
CADDYFILE_DST="/etc/caddy/Caddyfile"
SERVICE_SRC="${deploy_dir}/raspisanie-edge.service"
SERVICE_DST="/etc/systemd/system/raspisanie-edge.service"

# --- Цветной вывод (как в manage.sh) -------------------------------------------
if [[ "${NO_COLOR:-}" == "1" ]]; then
    C_OK=""; C_ERR=""; C_WARN=""; C_INFO=""; C_OFF=""
else
    C_OK=$'\033[32m'; C_ERR=$'\033[31m'; C_WARN=$'\033[33m'; C_INFO=$'\033[36m'; C_OFF=$'\033[0m'
fi
ok()   { printf '%s[OK]%s %s\n' "$C_OK" "$C_OFF" "$*"; }
fail() { printf '%s[FAIL]%s %s\n' "$C_ERR" "$C_OFF" "$*" >&2; }
warn() { printf '%s[WARN]%s %s\n' "$C_WARN" "$C_OFF" "$*"; }
info() { printf '%s[INFO]%s %s\n' "$C_INFO" "$C_OFF" "$*"; }
die()  { fail "$*"; exit 1; }

run_root() {
    # Выполняет команду от root: напрямую или через sudo.
    if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
        "$@"
    elif command -v sudo >/dev/null 2>&1; then
        sudo "$@"
    else
        die "Нужны права root (запустите под root или установите sudo)"
    fi
}

install_pkgs() {
    # install_pkgs <пакет...> — ставит системные пакеты через apt-get.
    [[ $# -gt 0 ]] || return 0
    command -v apt-get >/dev/null 2>&1 \
        || die "Поддерживается только Debian/Ubuntu (нет apt-get). Установите вручную: $*"
    run_root apt-get update -qq
    run_root env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "$@"
}

require_repo() {
    [[ -f "${EDGE_DIR}/requirements.txt" ]] \
        || die "В ${EDGE_DIR} нет requirements.txt — это не каталог репозитория raspisanie"
    [[ -d "$FRONTEND_DIR" ]] \
        || die "В ${EDGE_DIR} нет каталога frontend/"
}

# --- 1. Системные пакеты -------------------------------------------------------
install_system_packages() {
    info "Устанавливаю системные пакеты..."
    install_pkgs \
        python3 python3-venv python3-pip \
        curl ca-certificates gnupg \
        debian-keyring debian-archive-keyring apt-transport-https
    ok "Системные пакеты готовы"
}

# --- 2. Caddy ------------------------------------------------------------------
install_caddy() {
    if command -v caddy >/dev/null 2>&1; then
        ok "Caddy уже установлен: $(caddy version 2>/dev/null | head -1)"
        return 0
    fi
    info "Устанавливаю Caddy из официального apt-репозитория..."
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
        | run_root gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
        | run_root tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
    run_root apt-get update -qq
    run_root env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq caddy
    command -v caddy >/dev/null 2>&1 \
        || die "Caddy не установился — поставьте вручную: https://caddyserver.com/docs/install"
    ok "Caddy установлен: $(caddy version 2>/dev/null | head -1)"
}

# --- 3. Node 20 LTS ------------------------------------------------------------
node_major() {
    # Печатает major-версию установленного node или пусто.
    command -v node >/dev/null 2>&1 || return 0
    node --version 2>/dev/null | sed -E 's/^v([0-9]+).*/\1/'
}

install_node() {
    local major
    major="$(node_major)"
    if [[ -n "$major" && "$major" -ge 20 ]]; then
        ok "Node уже установлен: $(node --version) (npm $(npm --version 2>/dev/null || echo '?'))"
        return 0
    fi
    if [[ -n "$major" ]]; then
        warn "Node $(node --version) старше 20 — ставлю Node 20 LTS из NodeSource"
    else
        info "Node не найден — ставлю Node 20 LTS из NodeSource"
    fi
    install_pkgs ca-certificates curl gnupg
    curl -fsSL https://deb.nodesource.com/setup_20.x | run_root bash -
    run_root env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nodejs
    major="$(node_major)"
    [[ -n "$major" && "$major" -ge 20 ]] \
        || die "Не удалось поставить Node 20 (сейчас: $(node --version 2>/dev/null || echo 'нет')). Установите Node 20 вручную (nodesource/nvm) и повторите."
    ok "Node установлен: $(node --version) (npm $(npm --version 2>/dev/null || echo '?'))"
}

# --- 4. Python venv + зависимости ---------------------------------------------
setup_venv() {
    local py_bin=""
    local p
    for p in python3.13 python3.12 python3.11 python3; do
        if command -v "$p" >/dev/null 2>&1 \
            && "$p" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
            py_bin="$p"; break
        fi
    done
    [[ -n "$py_bin" ]] || die "Python 3.11+ не найден (нужен для edge-сервера)"

    if [[ -d "$VENV_DIR" ]]; then
        info "venv уже существует — обновляю зависимости"
    else
        "$py_bin" -m venv "$VENV_DIR" || die "Не удалось создать venv в ${VENV_DIR}"
    fi
    "$VENV_DIR/bin/pip" install --quiet --upgrade pip || warn "Не удалось обновить pip (не критично)"
    "$VENV_DIR/bin/pip" install --quiet -r "${EDGE_DIR}/requirements.txt" \
        || die "Не удалось установить Python-зависимости"
    ok "Python-зависимости установлены"
}

# --- 5. Сборка фронтенда --------------------------------------------------------
build_frontend() {
    info "Собираю фронтенд (npm ci && npm run build)..."
    (
        cd "$FRONTEND_DIR"
        # npm ci детерминирован от package-lock.json.
        npm ci
        npm run build
    ) || die "Сборка фронтенда не удалась — смотрите вывод npm выше"
    [[ -f "${DIST_DIR}/index.html" ]] \
        || die "После сборки нет ${DIST_DIR}/index.html — проверьте frontend/vite.config.ts"
    ok "Фронтенд собран: ${DIST_DIR}"
}

# --- 6. Пользователь, каталоги, .env -------------------------------------------
setup_user_dirs_env() {
    if id "$EDGE_USER" >/dev/null 2>&1; then
        info "Пользователь ${EDGE_USER} уже существует"
    else
        run_root useradd --system --create-home --shell /usr/sbin/nologin "$EDGE_USER" \
            || die "Не удалось создать пользователя ${EDGE_USER}"
        ok "Создан системный пользователь ${EDGE_USER}"
    fi

    info "Создаю каталог снапшота ${EDGE_SNAPSHOT_DIR}"
    run_root install -d -o "$EDGE_USER" -g "$EDGE_USER" -m 0750 "$EDGE_SNAPSHOT_DIR"

    if [[ -f "$EDGE_ENV_FILE" ]]; then
        info "Файл окружения ${EDGE_ENV_FILE} уже существует — не трогаю"
    else
        run_root cp "${deploy_dir}/edge.env.example" "$EDGE_ENV_FILE"
        run_root chown root:"$EDGE_USER" "$EDGE_ENV_FILE"
        run_root chmod 0640 "$EDGE_ENV_FILE"
        # Порт/путь снапшота из переменных установщика — чтобы .env совпадал с юнитом.
        run_root sed -i "s|^EDGE_PORT=.*|EDGE_PORT=${EDGE_PORT}|" "$EDGE_ENV_FILE"
        run_root sed -i "s|^SNAPSHOT_PATH=.*|SNAPSHOT_PATH=${EDGE_SNAPSHOT_DIR}/snapshot.json|" "$EDGE_ENV_FILE"
        warn "Создан ${EDGE_ENV_FILE}. Заполните секреты (EDGE_INGEST_SECRET, EDGE_AUTH_SECRET, VAPID_*) и повторите при необходимости."
    fi
}

# --- 7. Caddyfile --------------------------------------------------------------
install_caddyfile() {
    info "Устанавливаю /etc/caddy/Caddyfile"
    run_root install -d -m 0755 /etc/caddy
    # EDGE_DOMAIN/EDGE_PORT передаём непосредственно в Caddyfile через env-переменные
    # systemd-юнита Caddy (drop-in), чтобы не подменять текст конфига.
    printf 'EDGE_DOMAIN=%s\nEDGE_PORT=%s\n' "$EDGE_DOMAIN" "$EDGE_PORT" \
        | run_root tee /etc/caddy/edge.env >/dev/null
    run_root install -d -m 0755 /etc/systemd/system/caddy.service.d
    printf '[Service]\nEnvironmentFile=-/etc/caddy/edge.env\n' \
        | run_root tee /etc/systemd/system/caddy.service.d/edge.conf >/dev/null

    run_root cp "$CADDYFILE_SRC" "$CADDYFILE_DST"
    # Готовим каталог логов до старта Caddy.
    run_root install -d -o caddy -g caddy -m 0755 /var/log/caddy
    run_root caddy validate --config "$CADDYFILE_DST" --adapter caddyfile \
        || die "Caddyfile некорректен: ${CADDYFILE_DST}"
    ok "Caddyfile установлен и провалидирован (домен ${EDGE_DOMAIN}, порт ${EDGE_PORT})"
}

# --- 8. systemd-юнит -----------------------------------------------------------
install_service() {
    info "Устанавливаю systemd-юнит raspisanie-edge.service"
    # Подставляем реального пользователя/каталоги вместо плейсхолдеров.
    run_root sed \
        -e "s|^User=EDGE_USER|User=${EDGE_USER}|" \
        -e "s|^Group=EDGE_USER|Group=${EDGE_USER}|" \
        -e "s|^WorkingDirectory=EDGE_DIR|WorkingDirectory=${EDGE_DIR}|" \
        -e "s|^EnvironmentFile=EDGE_ENV_FILE|EnvironmentFile=${EDGE_ENV_FILE}|" \
        -e "s|^ExecStart=EDGE_DIR/|ExecStart=${EDGE_DIR}/|" \
        -e "s|^ReadWritePaths=EDGE_DIR EDGE_SNAPSHOT_DIR|ReadWritePaths=${EDGE_DIR} ${EDGE_SNAPSHOT_DIR}|" \
        "$SERVICE_SRC" | run_root tee "$SERVICE_DST" >/dev/null
    run_root systemctl daemon-reload
    run_root systemctl enable raspisanie-edge.service
    ok "Юнит установлен и включён в автозапуск"
}

reload_caddy() {
    if ! command -v systemctl >/dev/null 2>&1; then
        warn "systemd недоступен — запустите Caddy вручную: caddy run --config ${CADDYFILE_DST}"
        return 0
    fi
    run_root systemctl daemon-reload
    run_root systemctl enable caddy >/dev/null 2>&1 || true
    # reload мягко подхватывает новый конфиг; при ошибке — полный restart.
    run_root systemctl reload caddy >/dev/null 2>&1 \
        || run_root systemctl restart caddy
    ok "Caddy перезапущен с новым конфигом"
}

start_service() {
    run_root systemctl restart raspisanie-edge.service
    local waited=0
    while (( waited < 30 )); do
        if curl -sf "http://127.0.0.1:${EDGE_PORT}/healthz" >/dev/null 2>&1; then
            ok "Edge-сервер отвечает: http://127.0.0.1:${EDGE_PORT}/healthz"
            return 0
        fi
        sleep 2
        waited=$((waited + 2))
    done
    warn "Edge-сервер не ответил за 30 с. Проверьте: journalctl -u raspisanie-edge -n 50 --no-pager"
    return 0
}

main() {
    info "Установка edge-сервера публичного сайта"
    info "  домен:    ${EDGE_DOMAIN}"
    info "  порт:     ${EDGE_PORT}"
    info "  каталог:  ${EDGE_DIR}"
    info "  сервис:   ${EDGE_USER}"
    require_repo
    install_system_packages
    install_caddy
    install_node
    setup_venv
    build_frontend
    setup_user_dirs_env
    install_caddyfile
    install_service
    reload_caddy
    start_service
    echo
    ok "Готово!"
    info "Проверьте: https://${EDGE_DOMAIN}/healthz (после распространения DNS и выпуска сертификата)"
    info "Логи: journalctl -u raspisanie-edge -f   |   журнал Caddy: /var/log/caddy/edge-access.log"
}

main "$@"
