#!/usr/bin/env bash
# manage.sh — установка, обновление и эксплуатация Telegram-бота школьного расписания
# Использование: ./manage.sh <команда> [аргументы]
# Быстрая установка с нуля (без ручного клонирования):
#   curl -fsSL https://raw.githubusercontent.com/itdevlog/raspisanie/main/manage.sh | bash -s -- install
set -Eeuo pipefail

REPO_URL="https://github.com/itdevlog/raspisanie.git"
INSTALL_DIR_DEFAULT="/opt/raspisanie"

if [[ -n "${BASH_SOURCE[0]:-}" ]]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
else
    SCRIPT_DIR=""   # запущен из пайпа (curl | bash) — репозитория рядом нет
fi
SERVICE_NAME="tg-schedule-bot"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
VENV_DIR="${SCRIPT_DIR:-.}/.venv"
ENV_FILE="${SCRIPT_DIR:-.}/.env"
ENV_EXAMPLE="${SCRIPT_DIR:-.}/.env.example"
BACKUP_DIR="${SCRIPT_DIR:-.}/backups"
PID_FILE="${SCRIPT_DIR:-.}/bot.pid"
HEALTH_TIMEOUT=30

# Источник интерактивного ввода. При curl | bash stdin занят телом скрипта,
# поэтому вопросы читаем напрямую с терминала. Нет tty — пусто (ответы = дефолт).
INPUT_FD=""
if [[ -t 0 ]]; then
    INPUT_FD="/dev/stdin"
elif [[ -r /dev/tty ]]; then
    INPUT_FD="/dev/tty"
fi

is_repo() {
    # True если текущий SCRIPT_DIR — клон этого репозитория
    [[ -n "$SCRIPT_DIR" ]] \
        && [[ -f "${SCRIPT_DIR}/requirements.txt" ]] \
        && [[ -f "${SCRIPT_DIR}/.env.example" ]] \
        && git -C "$SCRIPT_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1
}

# --- Цветной вывод -----------------------------------------------------------
if [[ "${1:-}" == "--no-color" || "${NO_COLOR:-}" == "1" ]]; then
    C_OK=""; C_ERR=""; C_WARN=""; C_INFO=""; C_DIM=""; C_OFF=""
else
    C_OK=$'\033[32m'; C_ERR=$'\033[31m'; C_WARN=$'\033[33m'
    C_INFO=$'\033[36m'; C_DIM=$'\033[2m'; C_OFF=$'\033[0m'
fi

ok()   { printf '%s[OK]%s %s\n' "$C_OK" "$C_OFF" "$*"; }
fail() { printf '%s[FAIL]%s %s\n' "$C_ERR" "$C_OFF" "$*" >&2; }
warn() { printf '%s[WARN]%s %s\n' "$C_WARN" "$C_OFF" "$*"; }
info() { printf '%s[INFO]%s %s\n' "$C_INFO" "$C_OFF" "$*"; }
dim()  { printf '%s%s%s\n' "$C_DIM" "$*" "$C_OFF"; }
die()  { fail "$*"; exit 1; }

token_configured() {
    # True если в .env задан настоящий токен (не пусто и не заглушка)
    [[ -f "$ENV_FILE" ]] || return 1
    local token
    token=$(grep -E '^TELEGRAM_TOKEN=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)
    [[ -n "$token" && "$token" != *"YOUR_TELEGRAM_BOT_TOKEN"* && "$token" != *"123456789:ABCdef"* ]]
}

# --- Вспомогательные функции -------------------------------------------------
get_port() {
    if [[ -f "$ENV_FILE" ]]; then
        local port
        port=$(grep -E '^WEBAPP_PORT=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 || true)
        echo "${port:-8080}"
    else
        echo "8080"
    fi
}

systemd_available() { command -v systemctl >/dev/null 2>&1; }
service_exists() { systemd_available && systemctl list-unit-files "${SERVICE_NAME}.service" --no-legend 2>/dev/null | grep -q .; }
service_active() { service_exists && systemctl is-active --quiet "${SERVICE_NAME}.service"; }

run_root() {
    # Запускает команду от root: напрямую или через sudo
    if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
        "$@"
    elif command -v sudo >/dev/null 2>&1; then
        sudo "$@"
    else
        die "Нужны права root (запустите под root или установите sudo)"
    fi
}

system_pm() {
    # Определяет пакетный менеджер: apt-get / dnf / yum / apk, или пусто
    local pm
    for pm in apt-get dnf yum apk; do
        command -v "$pm" >/dev/null 2>&1 && { echo "$pm"; return 0; }
    done
    return 1
}

install_pkgs() {
    # install_pkgs <пакет...> — ставит системные пакеты через найденный PM
    [[ $# -gt 0 ]] || return 0
    local pm
    pm=$(system_pm) || die "Пакетный менеджер не найден — установите вручную: $*"
    case "$pm" in
        apt-get) run_root apt-get update -qq && run_root apt-get install -y -qq "$@" >/dev/null ;;
        dnf)     run_root dnf install -y -q "$@" ;;
        yum)     run_root yum install -y -q "$@" ;;
        apk)     run_root apk add --quiet "$@" ;;
    esac
}

ensure_cmd() {
    # ensure_cmd <команда> <пакеты...> — ставит пакеты, если команды нет
    local cmd="$1"; shift
    command -v "$cmd" >/dev/null 2>&1 && return 0
    warn "'${cmd}' не найден — потребуется установить: $*"
    confirm "Установить ($*)?" y || die "'${cmd}' обязателен. Установите вручную: $*"
    install_pkgs "$@" || die "Не удалось установить: $*"
    command -v "$cmd" >/dev/null 2>&1 || die "Команда '${cmd}' всё ещё недоступна после установки"
    ok "Установлено: $*"
}

service_running() {
    # True если бот запущен через systemd, вручную (bot.pid) или внешним процессом
    service_active && return 0
    if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        return 0
    fi
    external_pid >/dev/null
}

external_pid() {
    # PID процесса бота, запущенного без systemd/bot.pid (для stop/статуса).
    # Ищем только процессы с рабочим каталогом/путём = наш проект.
    local pid dir_pattern
    for pid in $(pgrep -f "python.*bot\.py" 2>/dev/null || true); do
        dir_pattern=$(readlink "/proc/${pid}/cwd" 2>/dev/null || true)
        if [[ "$dir_pattern" == "$SCRIPT_DIR" ]]; then
            echo "$pid"
            return 0
        fi
    done
    return 1
}

health_check() {
    # Успех если бот отвечает /healthz. При WEBAPP_PORT=0 — только проверка процесса.
    local port="$1" waited=0
    if [[ "$port" == "0" ]]; then
        service_running
        return $?
    fi
    while (( waited < HEALTH_TIMEOUT )); do
        if curl -sf "http://localhost:${port}/healthz" >/dev/null 2>&1; then
            return 0
        fi
        service_running || return 1
        sleep 2; waited=$((waited + 2))
    done
    return 1
}

do_stop() {
    if service_active; then
        systemctl stop "${SERVICE_NAME}.service" && ok "Сервис остановлен"
    elif [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        local pid
        pid=$(cat "$PID_FILE")
        kill "$pid" 2>/dev/null || true
        # Ждём до 10с корректного завершения (graceful shutdown бота)
        local waited=0
        while kill -0 "$pid" 2>/dev/null && (( waited < 10 )); do
            sleep 1; waited=$((waited + 1))
        done
        if kill -0 "$pid" 2>/dev/null; then
            warn "Процесс ${pid} не завершился за 10с — отправляю SIGKILL"
            kill -9 "$pid" 2>/dev/null || true
            sleep 1
        fi
        rm -f "$PID_FILE"
        ok "Процесс остановлен"
    elif external_pid >/dev/null; then
        local pid
        pid=$(external_pid)
        warn "Найден процесс бота (PID ${pid}), запущенный вне скрипта"
        if confirm "Остановить его?" y; then
            kill "$pid" && ok "Процесс остановлен"
        else
            info "Оставляю процесс как есть"
        fi
    else
        info "Бот не запущен"
    fi
}

do_start() {
    if ! token_configured; then
        die "Токен бота не задан в ${ENV_FILE}. Впишите TELEGRAM_TOKEN и повторите"
    fi
    if service_exists; then
        systemctl start "${SERVICE_NAME}.service" && ok "Сервис запущен"
    else
        if external_pid >/dev/null; then
            warn "Бот уже запущен (PID $(external_pid)) — не запускаю второй"
            return 0
        fi
        # Ручной запуск в фоне. exec внутри подкосой — чтобы bot.pid содержал
        # PID самого python, а не обёртки (иначе kill не достанет бота)
        ( cd "$SCRIPT_DIR" && exec nohup "$VENV_DIR/bin/python" bot.py >> "$SCRIPT_DIR/logs/bot.log" 2>&1 ) &
        local bgpid=$!
        echo "$bgpid" > "$PID_FILE"
        ok "Бот запущен вручную (PID ${bgpid})"
    fi
}

ask() {
    # ask <default> <prompt> -> ответ в $REPLY (EOF/нет tty -> дефолт)
    local default="$1"; shift
    local reply=""
    if [[ -n "$INPUT_FD" ]]; then
        read -r -p "$* ${C_DIM}[${default:-пусто}]:${C_OFF} " reply < "$INPUT_FD" || reply=""
    fi
    REPLY="${reply:-$default}"
}

confirm() {
    # confirm <prompt> <default y|n> -> rc=0 если «да» (EOF/нет tty -> дефолт)
    local prompt="$1" default="${2:-y}" reply=""
    if [[ -n "$INPUT_FD" ]]; then
        read -r -p "${prompt} [${default^^}] " reply < "$INPUT_FD" || reply=""
    fi
    reply="${reply:-$default}"
    [[ "${reply,,}" == "y" || "${reply,,}" == "да" ]]
}

# --- install -----------------------------------------------------------------
cmd_install() {
    # manage.sh мог быть скачан в пустую папку без репозитория
    if ! is_repo; then
        die "В ${SCRIPT_DIR:-текущем каталоге} нет репозитория бота (requirements.txt / .env.example).
Клонируйте: git clone ${REPO_URL}
Или используйте быструю установку: curl -fsSL <REPO>/manage.sh | bash -s -- install"
    fi
    info "Установка бота в ${SCRIPT_DIR}"

    # 1. Системные проверки
    ensure_cmd git git
    ensure_cmd curl curl

    local py_bin=""
    for p in python3.13 python3.12 python3.11 python3; do
        if command -v "$p" >/dev/null 2>&1; then
            "$p" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null && { py_bin="$p"; break; }
        fi
    done
    if [[ -z "$py_bin" ]]; then
        fail "Python 3.11+ не найден"
        local pm
        pm=$(system_pm) || die "Установите Python 3.11+ вручную: https://python.org"
        case "$pm" in
            apt-get) install_pkgs python3 python3-venv python3-pip ;;
            dnf|yum) install_pkgs python3 python3-pip ;;
            apk)     install_pkgs python3 py3-pip ;;
        esac || die "Не удалось установить Python"
        for p in python3.13 python3.12 python3.11 python3; do
            command -v "$p" >/dev/null 2>&1 && { py_bin="$p"; break; }
        done
        [[ -n "$py_bin" ]] || die "Python 3.11+ не найден после установки — обновите дистрибутив"
    fi
    ok "Python: $("$py_bin" --version)"

    if ! "$py_bin" -c 'import venv' 2>/dev/null; then
        warn "Модуль venv недоступен — устанавливаю"
        install_pkgs python3-venv || install_pkgs python3 || die "Установите python3-venv вручную"
        "$py_bin" -c 'import venv' 2>/dev/null || die "Модуль venv всё ещё недоступен"
    fi

    # 2. Виртуальное окружение
    if [[ -d "$VENV_DIR" ]]; then
        info "Виртуальное окружение уже существует — обновляю пакеты"
    else
        "$py_bin" -m venv "$VENV_DIR" || die "Не удалось создать venv в ${VENV_DIR}"
    fi
    "$VENV_DIR/bin/pip" install --quiet --upgrade pip \
        || warn "Не удалось обновить pip (не критично)"
    "$VENV_DIR/bin/pip" install --quiet -r "${SCRIPT_DIR}/requirements.txt" \
        || die "Не удалось установить зависимости"
    ok "Зависимости установлены ($(grep -cve '^\s*$' "${SCRIPT_DIR}/requirements.txt") пакетов)"

    # 3. Директории
    mkdir -p "${SCRIPT_DIR}"/{data,logs,cache,backups}
    ok "Директории data/ logs/ cache/ backups/ готовы"

    # 4. Конфигурация .env
    if [[ -f "$ENV_FILE" ]]; then
        info "Файл .env уже существует — пропускаю настройку"
    elif [[ -z "$INPUT_FD" ]]; then
        # Нет терминала (curl|bash без tty): не спрашиваем — только копия example
        cp "$ENV_EXAMPLE" "$ENV_FILE"
        warn "Скопирован .env.example -> .env (терминала нет — интерактив пропущен)"
        warn "Вставьте токен бота: nano ${ENV_FILE} и запустите ./manage.sh doctor"
    elif confirm "Настроить .env интерактивно?" y; then
        cp "$ENV_EXAMPLE" "$ENV_FILE"

        local token=""
        while [[ -z "$token" ]]; do
            ask "" "Введите токен бота (у @BotFather)"
            token="$REPLY"
            [[ -n "$token" ]] || warn "Токен не может быть пустым"
        done
        sed -i "s|^TELEGRAM_TOKEN=.*|TELEGRAM_TOKEN=${token}|" "$ENV_FILE"

        ask "" "ID администраторов через запятую (можно пусто)"
        sed -i "s|^ADMIN_IDS=.*|ADMIN_IDS=${REPLY}|" "$ENV_FILE"

        ask "3600" "Интервал обновления (сек)"
        sed -i "s|^UPDATE_INTERVAL=.*|UPDATE_INTERVAL=${REPLY}|" "$ENV_FILE"

        ask "8080" "Порт веб-версии (0 = отключить)"
        sed -i "s|^WEBAPP_PORT=.*|WEBAPP_PORT=${REPLY}|" "$ENV_FILE"

        ok ".env создан"
        warn "Проверьте .env: TIMEZONE, WEBAPP_URL при необходимости"
    else
        cp "$ENV_EXAMPLE" "$ENV_FILE"
        warn "Скопирован .env.example -> .env. Отредактируйте его: nano .env"
        info "После настройки запустите: ./manage.sh doctor"
    fi

    # 5. systemd
    if service_exists; then
        info "systemd-сервис уже установлен"
    elif systemd_available; then
        if confirm "Установить systemd-сервис (автозапуск)?" y; then
            install_service
        else
            info "Хорошо. Запуск вручную: ./manage.sh start"
        fi
    else
        info "systemd недоступен — запуск вручную: ./manage.sh start"
    fi

    echo
    ok "Установка завершена!"
    dim "Дальше: ./manage.sh doctor — проверка конфигурации"
    [[ -f "$ENV_FILE" ]] || dim "  1. Отредактируйте .env (токен бота!)"
    dim "  Запуск: ./manage.sh start"
    dim "  Логи:   ./manage.sh logs"
}

install_service() {
    cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Telegram School Schedule Bot
After=network.target

[Service]
Type=simple
User=${USER}
WorkingDirectory=${SCRIPT_DIR}
ExecStart=${VENV_DIR}/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload || die "systemctl daemon-reload не сработал"
    if token_configured; then
        systemctl enable --now "${SERVICE_NAME}.service" \
            || die "Не удалось запустить сервис. Проверьте: systemctl status ${SERVICE_NAME}"
        ok "systemd-сервис установлен и запущен (автозапуск включён)"
    else
        systemctl enable "${SERVICE_NAME}.service" >/dev/null \
            || die "Не удалось включить автозапуск сервиса"
        warn "Сервис установлен, но НЕ запущен: токен в .env не задан"
        info "Впишите TELEGRAM_TOKEN в ${ENV_FILE}, затем: ./manage.sh start"
    fi
    dim "Статус: systemctl status ${SERVICE_NAME}.service"
}

# --- update ------------------------------------------------------------------
cmd_update() {
    info "Обновление бота из GitHub"

    # 1. Чистое дерево
    if ! git -C "$SCRIPT_DIR" diff --quiet 2>/dev/null || ! git -C "$SCRIPT_DIR" diff --cached --quiet 2>/dev/null; then
        die "Локальные изменения в git — закоммитьте или сделайте git stash перед обновлением"
    fi
    local untracked
    untracked=$(git -C "$SCRIPT_DIR" ls-files --others --exclude-standard | grep -vE '^(data|logs|cache|backups)/' || true)
    if [[ -n "$untracked" ]]; then
        warn "Незакоммиченные файлы (обновятся только отслеживаемые):"
        dim "$untracked"
        confirm "Продолжить?" n || exit 1
    fi

    # 2. Свежесть
    info "Получаю изменения..."
    git -C "$SCRIPT_DIR" fetch origin || die "git fetch не удался — проверьте сеть"
    local current ahead remote_branch
    current=$(git -C "$SCRIPT_DIR" rev-parse HEAD)
    # origin/HEAD не всегда существует — берём upstream текущей ветки или origin/main
    remote_branch=$(git -C "$SCRIPT_DIR" rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null || echo "origin/main")
    ahead=$(git -C "$SCRIPT_DIR" rev-list --count "${current}..${remote_branch}" 2>/dev/null || echo "?")
    if [[ "$ahead" == "0" ]]; then
        ok "Уже актуальная версия"
        exit 0
    fi
    dim "Доступно новых коммитов: ${ahead}"

    # 3. Бэкап перед обновлением
    cmd_backup

    # 4. pull + зависимости
    info "Загружаю новую версию..."
    git -C "$SCRIPT_DIR" pull --ff-only origin || die "git pull не удался. Бэкап в ${BACKUP_DIR}"

    if [[ -d "$VENV_DIR" ]]; then
        "$VENV_DIR/bin/pip" install --quiet -r "${SCRIPT_DIR}/requirements.txt" \
            || { warn "Не удалось обновить зависимости — проверьте вручную"; }
    fi

    # 5. Рестарт + health-check + откат при сбое
    local was_running=false
    service_running && was_running=true
    if [[ "$was_running" != "true" ]]; then
        info "Бот не был запущен — только обновляю код, без запуска"
        git -C "$SCRIPT_DIR" log --oneline "${current}..HEAD" | head -20
        ok "Обновление завершено"
        return 0
    fi
    do_stop || true
    do_start

    info "Жду ответа /healthz (до ${HEALTH_TIMEOUT}с)..."
    if health_check "$(get_port)"; then
        echo
        ok "Обновление успешно! Новые коммиты:"
        git -C "$SCRIPT_DIR" log --oneline "${current}..HEAD" | head -20
        return 0
    fi

    # --- ОТКАТ ---
    echo
    fail "Бот не поднялся после обновления — откатываюсь"
    do_stop || true
    git -C "$SCRIPT_DIR" reset --hard "$current" || die "Не удалось откатить git!"
    warn "Откат к коммиту $(git -C "$SCRIPT_DIR" rev-parse --short "$current")"
    do_start || true
    if health_check "$(get_port)"; then
        warn "Откат успешен, бот работает на старой версии"
    else
        fail "Бот не поднялся даже после отката — смотрите логи: ./manage.sh logs"
    fi
    exit 1
}

# --- start / stop / restart / status -----------------------------------------
cmd_start() {
    do_start
    info "Жду ответа /healthz (до ${HEALTH_TIMEOUT}с)..."
    if health_check "$(get_port)"; then ok "Бот работает"; else warn "Health-check не прошёл — смотрите логи: ./manage.sh logs"; fi
    return 0
}

cmd_stop() { do_stop; }

cmd_restart() {
    do_stop || true
    do_start
    info "Жду ответа /healthz (до ${HEALTH_TIMEOUT}с)..."
    if health_check "$(get_port)"; then ok "Бот работает"; else warn "Health-check не прошёл — смотрите логи: ./manage.sh logs"; fi
    return 0
}

cmd_status() {
    echo "${C_INFO}=== Статус бота ===${C_OFF}"
    if service_exists; then
        if service_active; then
            ok "systemd: активен"
        else
            fail "systemd: неактивен"
        fi
        systemctl status "${SERVICE_NAME}.service" --no-pager -l | tail -n +1 || true
    elif [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        ok "Процесс вручную: PID $(cat "$PID_FILE")"
    elif external_pid >/dev/null; then
        ok "Процесс (внешний): PID $(external_pid)"
    else
        warn "Бот не запущен"
    fi

    local port
    port=$(get_port)
    if [[ "$port" == "0" ]]; then
        dim "Веб-сервер отключён (WEBAPP_PORT=0)"
    elif curl -sf "http://localhost:${port}/healthz" >/dev/null 2>&1; then
        ok "Веб /healthz: отвечает (порт ${port})"
    else
        warn "Веб /healthz: нет ответа (порт ${port})"
    fi
}

cmd_logs() {
    if service_exists && service_active; then
        journalctl -u "${SERVICE_NAME}.service" -f --no-pager -n 50
    elif [[ -f "${SCRIPT_DIR}/logs/bot.log" ]]; then
        tail -f "${SCRIPT_DIR}/logs/bot.log"
    else
        die "Логов ещё нет"
    fi
}

# --- backup / restore ---------------------------------------------------------
cmd_backup() {
    mkdir -p "$BACKUP_DIR"
    local stamp target
    stamp=$(date +%Y%m%d-%H%M%S)
    target="${BACKUP_DIR}/bot-backup-${stamp}.tar.gz"
    local files=()
    [[ -d "${SCRIPT_DIR}/data" ]] && files+=(data)
    [[ -f "$ENV_FILE" ]] && files+=(.env)
    [[ ${#files[@]} -eq 0 ]] && { warn "Нет данных для бэкапа (data/ и .env отсутствуют)"; return 0; }

    tar -czf "$target" -C "$SCRIPT_DIR" "${files[@]}" \
        || die "Не удалось создать бэкап"
    ok "Бэкап: ${target} ($(du -h "$target" | cut -f1))"

    # Храним последние 10
    local old
    old=$(find "$BACKUP_DIR" -name 'bot-backup-*.tar.gz' -printf '%T@ %p\n' 2>/dev/null | sort -rn | tail -n +11 | cut -d' ' -f2- || true)
    if [[ -n "$old" ]]; then
        dim "Удаляю старые бэкапы: $(wc -l <<< "$old") шт."
        while IFS= read -r f; do rm -f "$f"; done <<< "$old"
    fi
}

cmd_restore() {
    local latest
    latest=$(find "$BACKUP_DIR" -name 'bot-backup-*.tar.gz' -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2- || true)
    [[ -n "$latest" ]] || die "Бэкапов нет в ${BACKUP_DIR}"

    confirm "Восстановить ${latest}? Бот будет остановлен." n || exit 0
    do_stop || true
    tar -xzf "$latest" -C "$SCRIPT_DIR" || die "Не удалось распаковать бэкап"
    ok "Восстановлено из $(basename "$latest")"
    do_start
    if health_check "$(get_port)"; then ok "Бот работает"; else warn "Проверьте логи: ./manage.sh logs"; fi
    return 0
}

# --- doctor -------------------------------------------------------------------
cmd_doctor() {
    echo "${C_INFO}=== Диагностика ===${C_OFF}"
    local errors=0

    # Python / venv
    if [[ -d "$VENV_DIR" ]] && [[ -x "$VENV_DIR/bin/python" ]]; then
        ok "venv: $("$VENV_DIR"/bin/python --version 2>&1)"
    else
        fail "venv не найден — запустите: ./manage.sh install"
        errors=$((errors + 1))
    fi

    # Зависимости
    if [[ -x "$VENV_DIR/bin/python" ]] && "$VENV_DIR/bin/python" -c 'import telegram, fastapi, httpx' 2>/dev/null; then
        ok "Зависимости: установлены"
    else
        fail "Зависимости не установлены — запустите: ./manage.sh install"
        errors=$((errors + 1))
    fi

    # .env
    if [[ -f "$ENV_FILE" ]]; then
        ok ".env: найден"
        local token
        token=$(grep -E '^TELEGRAM_TOKEN=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)
        if [[ -z "$token" ]]; then
            fail "TELEGRAM_TOKEN: не задан"
            errors=$((errors + 1))
        elif [[ "$token" == *"YOUR_TELEGRAM_BOT_TOKEN"* || "$token" == *"123456789:ABCdef"* ]]; then
            fail "TELEGRAM_TOKEN: это заглушка из .env.example — вставьте реальный токен"
            errors=$((errors + 1))
        else
            ok "TELEGRAM_TOKEN: задан"
        fi
    else
        fail ".env не найден — cp .env.example .env"
        errors=$((errors + 1))
    fi

    # Директории
    local dir
    for dir in data logs cache; do
        if [[ -d "${SCRIPT_DIR}/${dir}" ]]; then
            ok "Директория ${dir}/: есть"
        else
            warn "Директория ${dir}/: нет (создастся при запуске)"
        fi
    done

    # Сервис / процесс
    if service_active; then
        ok "systemd-сервис: активен"
    elif [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        ok "Процесс: PID $(cat "$PID_FILE")"
    elif external_pid >/dev/null; then
        ok "Процесс (внешний): PID $(external_pid)"
    else
        warn "Бот не запущен — ./manage.sh start"
    fi

    # healthz
    local port
    port=$(get_port)
    if [[ "$port" == "0" ]]; then
        dim "Веб-сервер отключён (WEBAPP_PORT=0)"
    elif curl -sf "http://localhost:${port}/healthz" >/dev/null 2>&1; then
        ok "Веб /healthz: отвечает (порт ${port})"
    else
        warn "Веб /healthz: нет ответа (порт ${port})"
    fi

    echo
    if (( errors > 0 )); then
        fail "Проблем: ${errors}. Исправьте и повторите: ./manage.sh doctor"
        exit 1
    else
        ok "Все проверки пройдены"
    fi
}

# --- uninstall -----------------------------------------------------------------
cmd_uninstall() {
    echo "${C_WARN}Внимание: это остановит бота${C_OFF}"
    confirm "Продолжить удаление?" n || exit 0

    do_stop || true
    if service_exists; then
        systemctl disable "${SERVICE_NAME}.service" >/dev/null 2>&1 || true
        rm -f "$SERVICE_FILE" && systemctl daemon-reload
        ok "systemd-сервис удалён"
    fi

    if confirm "Удалить виртуальное окружение (.venv)?" n; then
        rm -rf "$VENV_DIR" && ok ".venv удалён"
    fi

    if confirm "Удалить данные и бэкапы (data/, backups/, .env)?" n; then
        rm -rf "${SCRIPT_DIR}/data" "${SCRIPT_DIR}/backups" "$ENV_FILE" && ok "Данные удалены"
    else
        info "Данные сохранены: data/, backups/, .env"
    fi
    ok "Удаление завершено. Код бота в ${SCRIPT_DIR} не тронут."
}

# --- usage ---------------------------------------------------------------------
cmd_help() {
    cat <<EOF
Управление Telegram-ботом школьного расписания

Использование: ./manage.sh <команда>

Быстрая установка с нуля (клонирует в ${INSTALL_DIR_DEFAULT}):
  curl -fsSL https://raw.githubusercontent.com/itdevlog/raspisanie/main/manage.sh | bash -s -- install

Команды:
  install     Полная установка: venv, зависимости, .env, systemd (интерактивно).
              Без репозитория рядом (curl|bash) — клонирует в ${INSTALL_DIR_DEFAULT} и устанавливает
  update      Обновление с GitHub + бэкап + откат при сбое
  start       Запуск бота
  stop        Остановка
  restart     Перезапуск
  status      Статус сервиса + health-check
  logs        Логи в реальном времени (Ctrl+C для выхода)
  backup      Бэкап data/ + .env в backups/ (хранит последние 10)
  restore     Восстановление из последнего бэкапа
  doctor      Диагностика: venv, зависимости, .env, сервис, /healthz
  uninstall   Остановка + удаление сервиса (с вопросами)
  help        Эта справка

Флаги:
  --no-color  Отключить цвета
EOF
}

# --- bootstrap (curl | bash) ----------------------------------------------------
cmd_bootstrap_install() {
    # Запущен из пайпа/скачан без репозитория: клонируем и передаём управление.
    # При curl | bash stdin занят самим скриптом — переключаем ввод на терминал,
    # если его нет (cron и т.п.) — все вопросы возьмут дефолты (confirm/ask устойчивы к EOF).
    info "Скрипт запущен вне репозитория — устанавливаю с GitHub"

    local install_dir="$INSTALL_DIR_DEFAULT"
    local reply=""
    if [[ -n "$INPUT_FD" ]]; then
        read -r -p "Каталог установки [${INSTALL_DIR_DEFAULT}]: " reply < "$INPUT_FD" || reply=""
    fi
    reply="${reply:-$INSTALL_DIR_DEFAULT}"
    install_dir="$reply"

    if [[ -d "$install_dir/.git" ]]; then
        info "Каталог ${install_dir} уже содержит репозиторий — обновляю код"
        ensure_cmd git git
        git -C "$install_dir" fetch origin 2>/dev/null || die "Не удалось обновить ${install_dir} из GitHub"
        git -C "$install_dir" reset --hard "$(git -C "$install_dir" rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null || echo origin/main)" >/dev/null
    elif [[ -e "$install_dir" ]]; then
        die "Каталог ${install_dir} занят — выберите другой путь установки"
    else
        info "Клонирую ${REPO_URL} -> ${install_dir}"
        ensure_cmd git git
        mkdir -p "$(dirname "$install_dir")"
        git clone "$REPO_URL" "$install_dir" || die "Не удалось клонировать репозиторий"
    fi

    # Доустанавливаем через manage.sh из клона (уже как обычный install)
    if [[ "${NO_COLOR:-}" == "1" ]]; then
        exec bash "$install_dir/manage.sh" --no-color install
    else
        exec bash "$install_dir/manage.sh" install
    fi
}

# --- main ----------------------------------------------------------------------
main() {
    if [[ "${1:-}" == "--no-color" ]]; then
        shift
    fi
    local cmd="${1:-help}"
    shift 2>/dev/null || true

    # Пайп (curl | bash) или manage.sh скачан без репозитория: работает только install (клонирует сам)
    if ! is_repo; then
        case "$cmd" in
            install) cmd_bootstrap_install ;;
            help|-h|--help|"") cmd_help ;;
            *) die "Эта команда работает только внутри установленного репозитория.
Быстрая установка с нуля: curl -fsSL https://raw.githubusercontent.com/itdevlog/raspisanie/main/manage.sh | bash -s -- install" ;;
        esac
        return
    fi

    case "$cmd" in
        install)   cmd_install ;;
        update)    cmd_update ;;
        start)     cmd_start ;;
        stop)      cmd_stop ;;
        restart)   cmd_restart ;;
        status)    cmd_status ;;
        logs)      cmd_logs ;;
        backup)    cmd_backup ;;
        restore)   cmd_restore ;;
        doctor)    cmd_doctor ;;
        uninstall) cmd_uninstall ;;
        help|-h|--help|"") cmd_help ;;
        *) die "Неизвестная команда: '${cmd}'. Смотрите: ./manage.sh help" ;;
    esac
}

main "$@"