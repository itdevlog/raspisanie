# 🚀 Прогон выката (runbook): origin + edge

Короткая операционная памятка: **как выкатить изменения и как проверить, что всё
живо**. Топология и переменные окружения — в [docs/EDGE.md](../../EDGE.md);
установка edge-хоста — в [deploy/edge/README.md](../../../deploy/edge/README.md).

```
Германия (origin, origin.3125.ru)          Москва (edge, 3125.ru)
бот + Telegram + Web Push   ──снапшот──▶   FastAPI + Caddy + собранный фронт
приватный VAPID-ключ                        (frontend/dist), только чтение
хранилище подписок                          прокси push-API на origin
```

Главное правило: **origin и edge обновляются отдельно**, и на каждом свой шаг.
Частая причина «ничего не изменилось» — обновили один хост и забыли второй.

---

## 0. Перед выкатом (на рабочей машине)

```bash
cd frontend && npm run verify     # svelte-check + eslint + vitest + build
cd .. && .venv/bin/python -m pytest -q
```

Мержим в `main` только зелёное: хосты тянут именно `origin/main`.

---

## 1. Origin (бот, рассылки, Web Push)

```bash
ssh <origin>
cd /opt/raspisanie
./manage.sh update
```

`update` делает всё сам: проверяет чистое дерево → `git fetch/pull --ff-only` →
бэкап → снимок зависимостей → `pip install -r requirements.txt` → рестарт →
ждёт `/healthz` (до 30 с) → **при провале сам откатывает** код и зависимости.

Важно:

- `git pull` руками **не заменяет** `update`: код обновится, но сервис не
  перезапустится и зависимости не подтянутся. Именно так однажды «пропал» пуш.
- Если сервис не был запущен, `update` только обновит код и не станет его
  поднимать (запуск — `./manage.sh start`).
- Когда новых коммитов нет, команда скажет «Уже актуальная версия» и выйдет.

---

## 2. Edge (публичный сайт и собранный фронт)

Бэкенд edge:

```bash
ssh <edge>
cd /opt/raspisanie
./manage.sh update        # нужен рестарт — web/*.py подхватываются только так
```

Фронтенд (статика отдаётся с диска, рестарт **не нужен**):

```bash
cd /opt/raspisanie/frontend
git fetch origin main && git reset --hard origin/main   # 1) СНАЧАЛА код
npm ci && npm run build                                 # 2) ПОТОМ сборка
grep -o 'index-[^"]*\.js' dist/index.html               # 3) хеш должен смениться
```

Порядок критичен: сборка **до** обновления кода оставляет `dist/` от старого
коммита — сайт выглядит «как раньше», хотя `HEAD` уже новый.

Если `npm ci` падает по памяти (на хосте ~550 МБ RAM), сначала добавьте swap:

```bash
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
```

`npm ci` нужен только при изменении `package-lock.json`/`node_modules`;
для обычной правки во `src/` достаточно `npm run build`.

---

## 3. Проверка после выката (мониторинг)

**Свежесть снапшота** — edge-эндпоинт `/healthz` (origin его так не отдаёт):

```bash
curl -s https://3125.ru/healthz
# {"status":"ok","snapshot_age_seconds":123,"generated_at":"...","version":2,"schools_count":17}
```

- `status` = `stale`, когда возраст снапшота превысил `SNAPSHOT_MAX_AGE`.
  Пустой store (снапшот ещё не получен) тоже `stale` — тогда проверяем публикацию
  на origin.
- `snapshot_age_seconds` — возраст последнего успешного ingest.

```bash
curl -s https://origin.3125.ru/healthz     # {"status":"ok"} — у origin только статус
```

**Web Push** (только на origin — там подписки и приватный ключ):

```bash
cd /opt/raspisanie
./manage.sh push-test --list               # что сохранено
./manage.sh push-test --send --all         # тестовая отправка
```

Ответ `404`/`410` от push-сервиса = мёртвый endpoint: подписка вычищается
автоматически, это нормальный фон, а не ошибка.

**Ошибки и метрики** (origin, без внешнего UI — всё в лог):

- `AlertService` (`bot.py`): повторяющаяся ошибка (≥3 раза за 5 минут по ключу
  «источник : тип») → **одно** сообщение админам в Telegram. Дедупликация не
  даёт спама на каждом цикле.
- `MetricsService`: агрегат счётчиков рассылок пишется в лог каждым циклом
  обновления.
- Логи обоих хостов: `./manage.sh logs` (там же видно публикацию снапшота и push).

**VAPID**: `./manage.sh vapid` печатает новую пару (в `.env` вписывается
вручную). Публичный ключ дублируется в `/etc/raspisanie-edge.env`, приватный
живёт только на origin. `VAPID_SUBJECT` — рабочий `mailto:`-адрес.

---

## 4. Частые проблемы

| Симптом | Причина | Что делать |
|---|---|---|
| Push не приходит | origin не обновлён/перезапущен | `./manage.sh update`, потом `push-test --send --all` |
| Сайт показывает старый UI | `npm run build` сделан до `git reset` | пересобрать после обновления кода (§2) |
| `python: command not found` | нет системного python | `./.venv/bin/python …` или `./manage.sh push-test`, `./manage.sh vapid` |
| `npm ci` падает | мало RAM | swap 2 ГБ (§2) |
| `/healthz` = `stale` | снапшот не публикуется | логи origin, статус публикации снапшота |
| Edge отдаёт 5xx | сервис лежит / плохой конфиг | `systemctl status raspisanie-edge`, `journalctl -u raspisanie-edge` |

Полный список команд: `./manage.sh help` (там же `doctor`, `backup`, `restore`,
`edge`, `vapid`, `push-test`).
