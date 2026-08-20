# django-script-consent

[English](#django-script-consent) · [Русский](#django-script-consent-русская-версия)

Reusable Django application for **explicit, granular consent to HTML/JS snippets** (analytics, marketing, widgets) with a **strict binding**: consent is valid only for the exact set of active scripts, load policy, and purpose text that existed when the user agreed.

- Django **4.2+** / **5.x** / **6.x** · Python **3.10–3.14**
- Python package: **`script_consent`** · settings: **`SCRIPT_CONSENT`**
- First-party signed consent cookie + server-side `ConsentRecord` audit log
- Ready-made banner (accept all / custom / necessary only / withdraw / dismiss)
- **Default UI language: English**, with Russian translations for chrome strings

> **Not** the PyPI project [`django-cookie-consent`](https://pypi.org/project/django-cookie-consent/) (django-commons). That package inventories HTTP cookies by group and can delete them; this package manages **script snippets** and re-prompts when the **script set or purpose text** changes.

---

## Key features

| Feature | Why it matters |
|--------|----------------|
| **`scripts_hash` strict mode** | Consent is cryptographically bound to the canonical set of active snippets (code, placement, category, `always_load` / `is_required`) **and** category purpose fields (title, description). Change Metrika code or the analytics blurb → old consent is invalid; the banner returns. |
| **Banner id + version** | Consent stores the **active banner row id** and version. Switching another `BannerConfig` (even at the same version number) invalidates prior consent. |
| **Admin-managed HTML/JS snippets** | Paste GTM, Metrika, pixels into admin with placement (`head` / `body_start` / `body_end`). No template deploy for every tracker change. |
| **Required vs consent-gated vs always-load** | Required categories and `always_load` snippets run without a prompt; optional snippets never load without a matching valid consent. |
| **Signed consent cookie** | Payload is Django-signed by default (`SIGNED_COOKIE=True`) with server-side `max_age`, HttpOnly on by default. |
| **Audit log** | Every accept / reject / custom / withdraw writes `ConsentRecord` (categories, banner version, hash, anonymized IP, User-Agent, optional user). |
| **Withdraw + dismiss** | Users can withdraw later; dismiss (X) only hides the banner until end of day and does **not** enable optional scripts. Withdraw clears dismiss so the banner can reappear. |
| **Out-of-the-box UI** | Neutral banner, category checkboxes, floating settings button, JS hooks (`ScriptConsent.open/close/withdraw`). |
| **Template tags *or* middleware** | Prefer `{% consent_scripts %}` / `{% consent_banner %}`; optional HTML injection middleware when you cannot edit the base template. |
| **Multi-process safe cache stamp** | Runtime snapshot uses a DB generation counter so LocMem workers do not serve stale snippets after admin changes. |
| **Retention command** | `purge_consent_records` + `CONSENT_RECORD_RETENTION_DAYS` for storage limitation. |

---

## Quick start

```bash
pip install django-script-consent
# development:
# pip install -e ".[dev]"
```

### settings.py

```python
INSTALLED_APPS = [
    # ...
    "script_consent",
]

MIDDLEWARE = [
    # ...
    "django.middleware.locale.LocaleMiddleware",  # recommended for i18n
    # ...
]

TEMPLATES = [
    {
        "OPTIONS": {
            "context_processors": [
                # ...
                "django.template.context_processors.request",  # required
                "script_consent.context_processors.script_consent",
            ],
        },
    },
]

LANGUAGE_CODE = "en"  # or "ru" for Russian UI chrome
USE_I18N = True

# optional
SCRIPT_CONSENT = {
    "PRIVACY_POLICY_URL": "/privacy/",
    "ANONYMIZE_IP": True,
    # "SHOW_SETTINGS_BUTTON": True,
}
```

### urls.py

```python
from django.urls import include, path

urlpatterns = [
    path("script-consent/", include("script_consent.urls")),
    # ...
]
```

### Migrate

```bash
python manage.py migrate script_consent
```

Creates default categories (`technical`, `analytics`, `marketing`) and a default English banner.

### Base template

```django
{% load script_consent %}
<!DOCTYPE html>
<html>
<head>
  {% consent_scripts "head" %}
</head>
<body>
  {% consent_scripts "body_start" %}

  {# site content #}

  {% consent_banner %}
  {% consent_scripts "body_end" %}
</body>
</html>
```

**Rules:**

- Snippets with `always_load=True` or a **required** category load **always**.
- Other optional snippets load **only** with valid consent for their category.
- The banner is shown only if there are consent-gated snippets and no valid consent (and the user has not dismissed the banner for today).

### Optional middleware

If you cannot edit the base template:

```python
MIDDLEWARE = [
    # ... after SessionMiddleware / CommonMiddleware
    # If you use GZipMiddleware, list ScriptConsentMiddleware *after* it
    # (process_response runs in reverse order: rewrite HTML, then gzip).
    "django.middleware.gzip.GZipMiddleware",
    "script_consent.middleware.ScriptConsentMiddleware",
]
```

Template tags remain the canonical integration; middleware is best-effort HTML injection (HTTP 200 `text/html` only).

---

## Settings (`SCRIPT_CONSENT`)

| Key | Default | Description |
|-----|---------|-------------|
| `CONSENT_COOKIE` | `script_consent` | Consent payload cookie |
| `DISMISS_COOKIE` | `script_banner_dismissed` | Banner dismiss (X) cookie |
| `CONSENT_ID_COOKIE` | `script_consent_id` | Optional plain UUID cookie name |
| `SET_CONSENT_ID_COOKIE` | `False` | Write the UUID cookie (payload already has `consent_id`) |
| `MAX_AGE` | 1 year | Consent cookie TTL (also enforces signed payload max age) |
| `DISMISS_MAX_AGE` | `None` | `None` = until end of local calendar day |
| `ANONYMIZE_IP` | `True` | Truncate IP stored in `ConsentRecord` |
| `TRUST_X_FORWARDED_FOR` | `False` | Use first `X-Forwarded-For` hop (only behind a trusted proxy) |
| `PRIVACY_POLICY_URL` | `/privacy/` | Link in the banner (`None` to hide; only `/…` or `http(s)://`) |
| `CACHE_TIMEOUT` | 3600 | Runtime cache TTL |
| `SIGNED_COOKIE` | `True` | Sign consent payload with Django signing |
| `COOKIE_SAMESITE` | `Lax` | |
| `COOKIE_SECURE` | `None` | `None` → `SESSION_COOKIE_SECURE` |
| `COOKIE_HTTPONLY` | `True` | HttpOnly on consent cookies |
| `SHOW_SETTINGS_BUTTON` | `True` | Floating “consent settings” button |
| `CONSENT_RECORD_RETENTION_DAYS` | `None` | Auto-purge window for `purge_consent_records` (`None` = keep) |

---

## Strict consent model

1. Cookie payload: `consent_id`, `categories`, `banner_id`, `banner_version`, `scripts_hash`.
2. Consent is **valid** only if active banner **id + version** and `scripts_hash` **exactly** match the server.
3. `scripts_hash` = SHA-256 over active snippets (including load-policy flags) **and** active category purpose fields (`is_required`, title, description). Changing policy or purpose text invalidates prior consent.
4. Closing with **X** is not consent: optional scripts stay off; banner stays hidden until the next day.
5. Withdraw: `POST /script-consent/withdraw/` + `ConsentRecord(action=withdraw)` (also clears the dismiss cookie).

| Method | URL | Purpose |
|--------|-----|---------|
| POST | `/script-consent/accept/` | `accept_all` / `reject_optional` / `custom` |
| POST | `/script-consent/dismiss/` | Close with X |
| POST | `/script-consent/withdraw/` | Withdraw consent |

After accept/withdraw the page reloads by default (correct placement of `head` scripts).

---

## Admin

- **Script categories** (`ScriptCategory`) — order, `is_required`, active flag
- **Script snippets** (`ScriptSnippet`) — placement (`head` / `body_start` / `body_end`), **load without consent**, code preview
- **Banner** — title/text; version bumps on text change or activation
- **Consent records** — read-only audit (no delete in admin; use `purge_consent_records`)

Snippet HTML/JS is rendered **unescaped** — only trusted staff should edit it.

---

## Customization

### Template

Override:

```
templates/script_consent/banner.html
```

### Styles

CSS variables in `script_consent/static/script_consent/css/banner.css`:

```css
:root {
  --cc-accent: #0f766e;
  --cc-bg: #fff;

  /* Floating button position (default bottom-right) */
  --cc-launcher-top: auto;
  --cc-launcher-right: 1.5rem;
  --cc-launcher-bottom: 2rem;
  --cc-launcher-left: auto;
  --cc-launcher-size: 3rem;

  /* One-shot attention pulse after banner close (0 = off) */
  --cc-launcher-attention: 1;
  --cc-launcher-attention-duration: 1.2s;
}
```

### JS callbacks

```js
window.ScriptConsent = {
  onAccept: function (categories) {},
  onRejectOptional: function () {},
  onCustom: function (categories) {},
  onDismiss: function () {},
  onWithdraw: function () {},
};

ScriptConsent.open();
ScriptConsent.close();
ScriptConsent.withdraw();
```

### Settings button

A floating settings icon (bottom-right by default) reopens the banner so users can change or reduce consent without project-specific footer links.

Disable:

```python
SCRIPT_CONSENT = {"SHOW_SETTINGS_BUTTON": False}
```

---

## Internationalization

- Default source language: **English**
- Bundled UI translations: **Russian** (`script_consent/locale/ru/`)
- Set `LANGUAGE_CODE = "ru"` (and `LocaleMiddleware`) to use Russian UI chrome
- Seeded banner/category **content** is English — edit in admin for Russian sites

```bash
# if you add new strings as a maintainer
django-admin makemessages -l ru -d django
django-admin compilemessages
```

---

## Example project

### Local

```bash
.venv/bin/python example_project/manage.py migrate
.venv/bin/python example_project/manage.py createsuperuser
.venv/bin/python example_project/manage.py runserver
```

Open http://127.0.0.1:8000/

### Docker

```bash
docker compose up --build
```

- Site: http://127.0.0.1:8000/
- Admin: http://127.0.0.1:8000/admin/ — default `admin` / `admin`

SQLite is stored in volume `example_db`. Reset: `docker compose down -v`.

---

## Tests

Python:

```bash
DJANGO_SETTINGS_MODULE=tests.settings .venv/bin/python -m django test tests -v 2
```

JavaScript (banner UI):

```bash
npm install
npm run test:js
```

## Development / CI checks

Install editable with dev dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run the same checks as CI (lint + format + type check + tests):

```bash
./check.sh
```

Auto-fix formatting where possible:

```bash
./check.sh --fix
```

The script runs: `ruff check`, `ruff format --check`, `black --check`, `isort --check-only`, `mypy script_consent tests`, Django tests, and JS tests. (`./scripts/check.sh` still works as an alias.)

---

## Privacy / compliance notes

The app supports informed, granular, and revocable consent, audit logging, and re-prompting when conditions change. It is **not legal advice**. Adapt banner copy and privacy policy to your jurisdiction and use case.

IP addresses in `ConsentRecord` are **anonymized by default** (IPv4 last octet / IPv6 /48). Full IP is not stored by the app unless `ANONYMIZE_IP=False`. Client IP is taken from `REMOTE_ADDR` unless `TRUST_X_FORWARDED_FOR=True` (use only behind a reverse proxy that overwrites `X-Forwarded-For`).

### Retention / erasure

`ConsentRecord` rows are read-only in admin (integrity of the audit log). For scheduled retention:

```bash
python manage.py purge_consent_records --days 365
# or configure SCRIPT_CONSENT["CONSENT_RECORD_RETENTION_DAYS"] and run without --days
python manage.py purge_consent_records --dry-run
```

### Runtime cache

Runtime state (snippets, hash, banner) is cached. Invalidation bumps a **DB-backed generation** counter so multi-process setups with `LocMemCache` still converge. Prefer a shared cache (Redis/Memcached) in production for performance.

---

## Comparison with django-cookie-consent (commons)

| | **django-script-consent** (this) | **django-cookie-consent** (commons) |
|--|----------------------------------|-------------------------------------|
| Focus | HTML/JS **snippets** + banner | Cookie **inventory** by group |
| Re-prompt | `scripts_hash` + banner id/version + purpose text | Group version = last cookie created |
| Middleware | Inject banner/scripts into HTML | **Delete** declined browser cookies |
| Consent storage | Signed JSON payload | Plain `group=version\|…` string |
| Audit | `ConsentRecord` (IP, UA, user, categories) | `LogItem` (action, group, version) |

---

## Source

- Primary: [gitverse.ru/lesbeg/django-cookie-consent](https://gitverse.ru/lesbeg/django-cookie-consent)
- Mirror: [github.com/anton-trapeznikov/django-cookie-consent](https://github.com/anton-trapeznikov/django-cookie-consent)

---
---

# django-script-consent (русская версия)

[English](#django-script-consent) · [Русский](#django-script-consent-русская-версия)

Переиспользуемое Django-приложение для **явного, гранулярного согласия на HTML/JS-сниппеты** (аналитика, маркетинг, виджеты) со **строгой привязкой**: согласие действительно только для того набора активных скриптов, политики загрузки и текста целей, которые были в момент согласия.

- Django **4.2+** / **5.x** / **6.x** · Python **3.10–3.14**
- Python-пакет: **`script_consent`** · настройки: **`SCRIPT_CONSENT`**
- Собственная подписанная cookie согласия + серверный журнал `ConsentRecord`
- Готовый баннер (принять всё / выборочно / только необходимые / отозвать / закрыть)
- **Язык UI по умолчанию: английский**, для chrome-строк есть русский перевод

> **Не** путать с пакетом на PyPI [`django-cookie-consent`](https://pypi.org/project/django-cookie-consent/) (django-commons). Тот ведёт **реестр HTTP-cookies** по группам и умеет их удалять; этот пакет управляет **сниппетами скриптов** и заново запрашивает согласие при **смене набора скриптов или текста целей**.

---

## Ключевые возможности

| Возможность | Зачем это нужно |
|-------------|-----------------|
| **Строгий режим `scripts_hash`** | Согласие привязано к каноническому набору активных сниппетов (код, placement, категория, `always_load` / `is_required`) **и** к полям целей категории (title, description). Сменили код Метрики или формулировку analytics → старое согласие недействительно, баннер снова показывается. |
| **Banner id + version** | В cookie сохраняются **id активной строки баннера** и версия. Переключение на другой `BannerConfig` (даже с той же цифрой version) инвалидирует прежнее согласие. |
| **Сниппеты HTML/JS из админки** | GTM, Метрика, пиксели — вставка в admin с placement (`head` / `body_start` / `body_end`). Не нужно деплоить шаблоны ради каждого трекера. |
| **Required / gated / always-load** | Обязательные категории и `always_load` грузятся без запроса; опциональные — **только** при валидном согласии на категорию. |
| **Подписанная cookie согласия** | По умолчанию Django signing (`SIGNED_COOKIE=True`), серверный `max_age`, HttpOnly включён. |
| **Журнал аудита** | Каждый accept / reject / custom / withdraw пишет `ConsentRecord` (категории, версия баннера, hash, анонимизированный IP, User-Agent, опционально user). |
| **Withdraw + dismiss** | Пользователь может отозвать согласие позже; «X» только скрывает баннер до конца дня и **не** включает опциональные скрипты. Withdraw сбрасывает dismiss, чтобы баннер мог появиться снова. |
| **UI из коробки** | Нейтральный баннер, чекбоксы категорий, плавающая кнопка настроек, JS-хуки (`ScriptConsent.open/close/withdraw`). |
| **Template tags *или* middleware** | Предпочтительно `{% consent_scripts %}` / `{% consent_banner %}`; опциональный middleware для инъекции HTML, если base-шаблон нельзя править. |
| **Кэш, безопасный для multi-process** | Снимок runtime использует DB-счётчик generation — воркеры с LocMem не отдают устаревшие сниппеты после правок в admin. |
| **Команда retention** | `purge_consent_records` + `CONSENT_RECORD_RETENTION_DAYS` для ограничения срока хранения. |

---

## Быстрый старт

```bash
pip install django-script-consent
# разработка:
# pip install -e ".[dev]"
```

### settings.py

```python
INSTALLED_APPS = [
    # ...
    "script_consent",
]

MIDDLEWARE = [
    # ...
    "django.middleware.locale.LocaleMiddleware",  # рекомендуется для i18n
    # ...
]

TEMPLATES = [
    {
        "OPTIONS": {
            "context_processors": [
                # ...
                "django.template.context_processors.request",  # обязательно
                "script_consent.context_processors.script_consent",
            ],
        },
    },
]

LANGUAGE_CODE = "ru"  # или "en"
USE_I18N = True

# опционально
SCRIPT_CONSENT = {
    "PRIVACY_POLICY_URL": "/privacy/",
    "ANONYMIZE_IP": True,
    # "SHOW_SETTINGS_BUTTON": True,
}
```

### urls.py

```python
from django.urls import include, path

urlpatterns = [
    path("script-consent/", include("script_consent.urls")),
    # ...
]
```

### Миграции

```bash
python manage.py migrate script_consent
```

Создаёт категории по умолчанию (`technical`, `analytics`, `marketing`) и баннер (текст на английском — переведите в admin).

### Базовый шаблон

```django
{% load script_consent %}
<!DOCTYPE html>
<html>
<head>
  {% consent_scripts "head" %}
</head>
<body>
  {% consent_scripts "body_start" %}

  {# контент сайта #}

  {% consent_banner %}
  {% consent_scripts "body_end" %}
</body>
</html>
```

**Правила:**

- Сниппеты с `always_load=True` или из **обязательной** категории грузятся **всегда**.
- Остальные опциональные — **только** при валидном согласии на их категорию.
- Баннер показывается, если есть consent-gated сниппеты, нет валидного согласия и баннер не закрыт (dismiss) на сегодня.

### Опциональный middleware

Если base-шаблон нельзя править:

```python
MIDDLEWARE = [
    # ... после SessionMiddleware / CommonMiddleware
    # При GZipMiddleware указывайте ScriptConsentMiddleware *после* него
    # (process_response идёт в обратном порядке: правка HTML, затем gzip).
    "django.middleware.gzip.GZipMiddleware",
    "script_consent.middleware.ScriptConsentMiddleware",
]
```

Каноническая интеграция — template tags; middleware — best-effort (только HTTP 200 и `text/html`).

---

## Настройки (`SCRIPT_CONSENT`)

| Ключ | По умолчанию | Описание |
|------|--------------|----------|
| `CONSENT_COOKIE` | `script_consent` | Cookie с payload согласия |
| `DISMISS_COOKIE` | `script_banner_dismissed` | Cookie закрытия баннера (X) |
| `CONSENT_ID_COOKIE` | `script_consent_id` | Имя опциональной cookie с UUID |
| `SET_CONSENT_ID_COOKIE` | `False` | Писать UUID-cookie (id уже внутри payload) |
| `MAX_AGE` | 1 год | TTL cookie согласия (и max_age подписи) |
| `DISMISS_MAX_AGE` | `None` | `None` = до конца локальных суток |
| `ANONYMIZE_IP` | `True` | Обрезать IP в `ConsentRecord` |
| `TRUST_X_FORWARDED_FOR` | `False` | Брать первый hop `X-Forwarded-For` (только за доверенным proxy) |
| `PRIVACY_POLICY_URL` | `/privacy/` | Ссылка в баннере (`None` — скрыть; только `/…` или `http(s)://`) |
| `CACHE_TIMEOUT` | 3600 | TTL runtime-кэша |
| `SIGNED_COOKIE` | `True` | Подпись payload через Django signing |
| `COOKIE_SAMESITE` | `Lax` | |
| `COOKIE_SECURE` | `None` | `None` → `SESSION_COOKIE_SECURE` |
| `COOKIE_HTTPONLY` | `True` | HttpOnly на cookies согласия |
| `SHOW_SETTINGS_BUTTON` | `True` | Плавающая кнопка «настройки согласия» |
| `CONSENT_RECORD_RETENTION_DAYS` | `None` | Окно purge (`None` = хранить всегда) |

---

## Строгая модель согласия

1. Payload cookie: `consent_id`, `categories`, `banner_id`, `banner_version`, `scripts_hash`.
2. Согласие **валидно**, только если **id + version** активного баннера и `scripts_hash` **точно** совпадают с сервером.
3. `scripts_hash` = SHA-256 по активным сниппетам (включая флаги загрузки) **и** полям целей категорий (`is_required`, title, description). Смена политики или текста целей инвалидирует согласие.
4. Закрытие **X** — не согласие: опциональные скрипты выключены; баннер скрыт до следующего дня.
5. Отзыв: `POST /script-consent/withdraw/` + `ConsentRecord(action=withdraw)` (также очищает dismiss-cookie).

| Метод | URL | Назначение |
|--------|-----|------------|
| POST | `/script-consent/accept/` | `accept_all` / `reject_optional` / `custom` |
| POST | `/script-consent/dismiss/` | Закрыть крестиком |
| POST | `/script-consent/withdraw/` | Отозвать согласие |

После accept/withdraw страница по умолчанию перезагружается (корректная вставка `head`-скриптов).

---

## Админка

- **Категории скриптов** (`ScriptCategory`) — порядок, `is_required`, активность
- **Сниппеты** (`ScriptSnippet`) — placement, **загрузка без согласия**, превью кода
- **Баннер** — title/text; версия растёт при смене текста или активации
- **Записи согласия** — только чтение (удаление в admin запрещено; используйте `purge_consent_records`)

HTML/JS сниппетов выводится **без экранирования** — редактировать должен только доверенный staff.

---

## Кастомизация

### Шаблон

Переопределите:

```
templates/script_consent/banner.html
```

### Стили

CSS-переменные в `script_consent/static/script_consent/css/banner.css`:

```css
:root {
  --cc-accent: #0f766e;
  --cc-bg: #fff;

  --cc-launcher-top: auto;
  --cc-launcher-right: 1.5rem;
  --cc-launcher-bottom: 2rem;
  --cc-launcher-left: auto;
  --cc-launcher-size: 3rem;

  --cc-launcher-attention: 1;
  --cc-launcher-attention-duration: 1.2s;
}
```

### JS-колбэки

```js
window.ScriptConsent = {
  onAccept: function (categories) {},
  onRejectOptional: function () {},
  onCustom: function (categories) {},
  onDismiss: function () {},
  onWithdraw: function () {},
};

ScriptConsent.open();
ScriptConsent.close();
ScriptConsent.withdraw();
```

### Кнопка настроек

Плавающая иконка настроек (по умолчанию справа снизу) снова открывает баннер — смена или уменьшение согласия без отдельной ссылки в футере.

Отключить:

```python
SCRIPT_CONSENT = {"SHOW_SETTINGS_BUTTON": False}
```

---

## Интернационализация

- Исходный язык строк: **английский**
- В комплекте UI-перевод: **русский** (`script_consent/locale/ru/`)
- `LANGUAGE_CODE = "ru"` (+ `LocaleMiddleware`) — русские кнопки/лейблы
- **Контент** баннера и категорий из seed — на английском; для RU-сайтов переведите в admin

```bash
django-admin makemessages -l ru -d django
django-admin compilemessages
```

---

## Пример проекта

### Локально

```bash
.venv/bin/python example_project/manage.py migrate
.venv/bin/python example_project/manage.py createsuperuser
.venv/bin/python example_project/manage.py runserver
```

http://127.0.0.1:8000/

### Docker

```bash
docker compose up --build
```

- Сайт: http://127.0.0.1:8000/
- Admin: http://127.0.0.1:8000/admin/ — по умолчанию `admin` / `admin`

SQLite в volume `example_db`. Сброс: `docker compose down -v`.

---

## Тесты

Python:

```bash
DJANGO_SETTINGS_MODULE=tests.settings .venv/bin/python -m django test tests -v 2
```

JavaScript (UI баннера):

```bash
npm install
npm run test:js
```

## Разработка / CI-проверки

Установка в editable-режиме с dev-зависимостями:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Запуск тех же проверок, что и в CI (линтинг, форматирование, типы, тесты):

```bash
./check.sh
```

Автоисправление форматирования, где возможно:

```bash
./check.sh --fix
```

Скрипт выполняет: `ruff check`, `ruff format --check`, `black --check`, `isort --check-only`, `mypy script_consent tests`, Django-тесты и JS-тесты. (`./scripts/check.sh` — алиас.)

---

## Приватность / compliance

Приложение поддерживает информированное, гранулярное и отзывное согласие, аудит и повторный запрос при смене условий. Это **не юридическая консультация**. Адаптируйте тексты и политику под вашу юрисдикцию.

IP в `ConsentRecord` **по умолчанию анонимизируется** (IPv4 — последний октет / IPv6 — /48). Полный IP не пишется, пока `ANONYMIZE_IP=False`. IP берётся из `REMOTE_ADDR`, если не включён `TRUST_X_FORWARDED_FOR=True` (только за reverse proxy, который **перезаписывает** `X-Forwarded-For`).

### Срок хранения / удаление

Строки `ConsentRecord` в admin только на чтение (целостность журнала). Для регламентной очистки:

```bash
python manage.py purge_consent_records --days 365
# или SCRIPT_CONSENT["CONSENT_RECORD_RETENTION_DAYS"] и вызов без --days
python manage.py purge_consent_records --dry-run
```

### Runtime-кэш

Состояние (сниппеты, hash, баннер) кэшируется. Инвалидация увеличивает **generation в БД**, поэтому multi-process + LocMem всё равно сходятся. В production предпочтителен общий кэш (Redis/Memcached).

---

## Сравнение с django-cookie-consent (commons)

| | **django-script-consent** (этот пакет) | **django-cookie-consent** (commons) |
|--|----------------------------------------|-------------------------------------|
| Фокус | **Сниппеты** HTML/JS + баннер | **Реестр cookies** по группам |
| Повторный запрос | `scripts_hash` + banner id/version + текст целей | Версия группы = created последнего cookie |
| Middleware | Инъекция баннера/скриптов в HTML | **Удаление** declined cookies в браузере |
| Хранение согласия | Подписанный JSON | Строка `group=version\|…` |
| Аудит | `ConsentRecord` (IP, UA, user, категории) | `LogItem` (action, group, version) |

---

## Исходники

- Основной: [gitverse.ru/lesbeg/django-cookie-consent](https://gitverse.ru/lesbeg/django-cookie-consent)
- Зеркало: [github.com/anton-trapeznikov/django-cookie-consent](https://github.com/anton-trapeznikov/django-cookie-consent)
