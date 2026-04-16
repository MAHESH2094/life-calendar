# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive test suite (74 tests across engine, CLI, and auto-update)
- `ruff` linting + `pytest-cov` coverage in CI pipeline
- Codecov integration for coverage tracking
- Docker entrypoint with graceful shutdown (SIGTERM/SIGINT handling)
- Non-root Docker user for security
- Rate-limit guard in auto-updater (skip if PNG < 5 min old)
- `CODE_OF_CONDUCT.md` (Contributor Covenant)
- `CONTRIBUTING.md` with setup instructions
- GitHub issue templates (bug report, feature request)
- Pull request template with checklist
- `CHANGELOG.md` (this file)

### Fixed
- `life_calendar_cli.py`: `_ensure_config()` no longer crashes when config file doesn't exist yet

## [2.0.0] - 2025-02-19

### Added
- Multi-mode calendar: Life in Weeks, Year Progress, Goal Countdown
- Tkinter GUI with Enter/Esc shortcuts
- Headless wallpaper engine (`wallpaper_engine.py`)
- Auto-updater (`auto_update.py`) for Task Scheduler / cron
- CLI helper (`life_calendar_cli.py`) for setup automation
- Windows EXE builder (`build_exe.py`)
- Docker + docker-compose support
- Multi-OS wallpaper setter (Windows, macOS, Linux with 6 DE support)
- Atomic file locking with PID verification
- Rotating log handler (500KB, 3 backups)
- DPI awareness for Windows
- Config versioning and migration

## [1.0.0] - 2025-01-01

### Added
- Initial release with basic life-in-weeks wallpaper generation
