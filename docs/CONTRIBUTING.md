# Contributing to Life Calendar

Thanks for your interest in contributing! Here's how to get started.

## Quick Start

```bash
# 1. Fork & clone
git clone https://github.com/<your-username>/life-calendar.git
cd life-calendar

# 2. Create a virtual environment
python -m venv .venv
.venv/Scripts/activate   # Windows
# source .venv/bin/activate  # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt
pip install pytest pytest-cov ruff

# 4. Run tests
pytest -v

# 5. Run linter
ruff check . --select E,F,W
```

## Development Workflow

1. **Create a branch** from `main` for your feature or fix
2. **Write tests** for any new functionality (see `tests/` folder)
3. **Run the test suite** before submitting – all tests must pass
4. **Run ruff** – fix any lint errors
5. **Submit a PR** with a clear description of what you changed and why

## Code Style

- We use **ruff** for linting (rules: E, F, W)
- **Before submitting a PR**, run `ruff check .` locally and fix any errors
  ```bash
  ruff check . --select E,F,W  # Shows all issues
  ruff check . --fix            # Auto-fixes common issues
  ```
- The CI pipeline enforces ruff checks – PRs with lint errors will fail
- Keep functions focused and well-documented
- Use type hints where possible
- Follow the existing architecture: Engine (headless) → GUI (optional) → CLI (helper)

## Project Structure

| File | Purpose |
|------|---------|
| `wallpaper_engine.py` | Core generation logic (headless, no GUI) |
| `life_calendar_gui.py` | Tkinter GUI for configuration |
| `life_calendar_cli.py` | CLI helper (cron/task setup) |
| `auto_update.py` | Headless updater for schedulers |
| `build_exe.py` | PyInstaller build script |
| `tests/` | pytest test suite |

## Reporting Issues

Please use the [issue templates](https://github.com/MAHESH2094/life-calendar/issues/new/choose) to report bugs or request features.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
