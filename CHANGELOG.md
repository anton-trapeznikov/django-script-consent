# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-08-02

### Breaking
- `BannerConfig.get_solo()` no longer invents a banner: it returns the active row or `None`.
  Inactive rows are **not** reactivated and a default is **not** created on read.
  Seed data remains the responsibility of migrations and admin.
- Without an active banner the consent dialog is not shown; `POST /accept/` returns
  `400` with `{"ok": false, "error": "no_active_banner"}`. Required / `always_load`
  scripts still inject.

### Changed
- Internal layout: former `utils.py` replaced by focused modules `cache`, `consent`,
  `cookies`, `hashing`, `ip`, `services`, and `repositories` (ORM boundary).
  The `script_consent.utils` module is removed — import from those modules directly.
- Default `COOKIE_HTTPONLY` is `True`.
- Signed consent cookies enforce `MAX_AGE` via `signing.loads(..., max_age=...)`.
- `X-Forwarded-For` is ignored unless `TRUST_X_FORWARDED_FOR=True`.
- Optional `script_consent_id` cookie is not set by default (`SET_CONSENT_ID_COOKIE=False`).
- Accept path creates `ConsentRecord` + M2M inside `transaction.atomic`.
- Middleware injects only into HTTP 200 HTML responses.
- `ConsentRecord` remains fully read-only in admin (no delete); use `purge_consent_records` for retention.
- Test suite reorganized into `tests/unit/` (mocked) and `tests/integration/`.

### Fixed
- `scripts_hash` now includes category `is_required` / load policy and purpose text (title, description), so flipping a category to required or changing purpose invalidates prior consent.
- Consent is bound to active **banner id + version**; switching active `BannerConfig` invalidates consent even when versions match.
- Runtime cache invalidation uses a DB generation stamp so multi-worker LocMem caches do not serve stale snippets until TTL.
- `withdraw` clears the dismiss cookie so the banner can reappear after withdrawal.
- Context processor / middleware / template tag no longer double-fetch valid consent.

### Added
- Setting `CONSENT_RECORD_RETENTION_DAYS` and management command `purge_consent_records`.
- Setting `TRUST_X_FORWARDED_FOR`, `SET_CONSENT_ID_COOKIE`.
- Privacy policy URL sanitization (relative or `http(s)` only).

## [0.1.0] - 2026-07-19

### Added
- Initial release of `django-script-consent`.
- Explicit, granular consent with strict binding to active scripts (`scripts_hash`).
- Default categories: `technical`, `analytics`, `marketing`.
- Banner with accept all / accept selected / necessary only actions.
- Withdraw consent endpoint.
- Server-side `ConsentRecord` audit log with anonymized IP addresses.
- Django admin for categories, scripts, banner, and read-only consent records.
- Template tags (`consent_scripts`, `consent_banner`) and optional middleware for HTML injection.
- Floating consent settings button.
- Russian translations for UI strings.
- Example project with Docker support.
- Test suite with high code coverage.
