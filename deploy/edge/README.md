# deploy/edge — публичный сайт расписания (Москва)

Развёртывание edge-хоста: Caddy с автоматическим TLS на `.ru`-домене,
FastAPI/uvicorn edge-сервер (`python -m web.edge_server`), systemd-сервис.
Origin (Германия) остаётся ботом и публикует снапшот сюда.

```
Интернет ──HTTPS──▶ Caddy (.ru, авто-TLS) ──▶ 127.0.0.1:EDGE_PORT (FastAPI)
                                                   ▲
Origin (Германия) ── POST /internal/snapshot (HMAC)┘
```

## Быстрый старт

```bash
# На чистом Debian-хосте, из корня репозитория:
sudo EDGE_DOMAIN=raspisanie.example.ru bash deploy/edge/install.sh
```

Скрипт идемпотентен: повторный запуск обновляет код, пересобирает фронтенд и
перезапускает сервис. Требуются открытые порты 80/443 и A-запись домена на этот
сервер (иначе Let's Encrypt не выпустит сертификат).

Переменные установщика: `EDGE_DOMAIN`, `EDGE_PORT`, `EDGE_USER`, `EDGE_DIR`,
`EDGE_ENV_FILE`, `EDGE_SNAPSHOT_DIR` (см. шапку `install.sh`).

## Файлы

| Файл | Назначение |
|------|------------|
| `Caddyfile` | vhost `.ru`: авто-TLS, gzip/zstd, `reverse_proxy` на `127.0.0.1:EDGE_PORT`. |
| `raspisanie-edge.service` | systemd-юнит (шаблон; `install.sh` подставляет пути/пользователя). |
| `install.sh` | Установка: Caddy, Node 20 LTS, venv, сборка фронтенда, снапшот-каталог, сервис. |
| `edge.env.example` | Образец `/etc/raspisanie-edge.env` со всеми переменными edge. |

## Конфигурация

`install.sh` создаёт `/etc/raspisanie-edge.env` (права `0640`, владелец root)
из `edge.env.example` и подключает его к сервису через `EnvironmentFile`.
Заполните секреты на сервере (в репозиторий не коммитятся):

- `EDGE_INGEST_SECRET` — HMAC-секрет входящего снапшота (совпадает с origin);
- `EDGE_AUTH_SECRET` — общий секрет origin↔edge для прокси push;
- `EDGE_ORIGIN_URL` — базовый URL origin для прокси push;
- `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` / `VAPID_SUBJECT` — Web Push.

Домен и порт Caddy задаются не текстом в `Caddyfile`, а env-переменными
`EDGE_DOMAIN`/`EDGE_PORT` через drop-in `/etc/systemd/system/caddy.service.d/edge.conf`
и `/etc/caddy/edge.env`; в `Caddyfile` это `{$EDGE_DOMAIN:...}` и
`{$EDGE_PORT:...}` с безопасными плейсхолдерами.

## SPA-fallback: решение и обоснование

Бриф W26 упоминает `try_files`/SPA-fallback «в Caddy», но авторитетная
реализация уже живёт в приложении — `web/api.py::SPAStaticFiles` (W22). Чтобы
не было двух конфликтующих механизмов, принято решение:

- **Авторитетный SPA-fallback — в приложении.** `SPAStaticFiles` отдаёт
  `index.html` для клиентских deep-link'ов (`/s/{school}/...`) и **честный 404**
  для `/api`, `/internal`, `/healthz` (у них не должно быть HTML-тела
  приложения). Uvicorn остаётся единственным местом, знающим про префиксы API.
- **Caddy только проксирует.** В `Caddyfile` нет `try_files` и нет раздачи
  `frontend/dist` напрямую: любая такая логика либо замаскировала бы `/api/*` и
  `/internal/*` статикой, либо продублировала бы `SPAStaticFiles` с риском
  расхождения. `reverse_proxy 127.0.0.1:EDGE_PORT` — самый простой корректный
  вариант. `/api/*`, `/internal/*` и `/healthz` гарантированно уходят в FastAPI.

Так `frontend/dist` (собранный Vite-сборкой) отдаётся приложением (mount `/`
последним), а Caddy отвечает только за TLS/HTTP-обвязку и клиентский IP.

## X-Forwarded-For и rate-limit (важно)

Rate-limit edge доверяет `X-Forwarded-For` **только** если непосредственный пир
— `127.0.0.1` (W8: `create_edge_app` доверяет литералу `127.0.0.1`), и берёт
**левое** значение заголовка как IP клиента.

Безопасность держится на поведении Caddy по умолчанию: при `reverse_proxy` без
блока `trusted_proxies` Caddy **заменяет** входящий `X-Forwarded-For` адресом
наблюдаемого пира (реального клиента), а не дописывает присланный извне
заголовок. Поэтому левое значение достоверно.

**В `Caddyfile` намеренно НЕТ** `trusted_proxies` и `trusted_proxies_strict off`.
Если их добавить, Caddy начнёт доверять присланному клиентом XFF и подставит его
левым — клиент подделает IP и обойдёт rate-limit. Не добавляйте.

## Проверка

```bash
# Локально, без реального хоста:
shellcheck --severity=warning deploy/edge/install.sh
bash -n deploy/edge/install.sh
caddy validate --config deploy/edge/Caddyfile --adapter caddyfile

# На сервере после установки:
curl -sf http://127.0.0.1:8090/healthz | python3 -m json.tool
curl -sf https://raspisanie.example.ru/healthz
systemctl status raspisanie-edge
journalctl -u raspisanie-edge -n 50 --no-pager
```
