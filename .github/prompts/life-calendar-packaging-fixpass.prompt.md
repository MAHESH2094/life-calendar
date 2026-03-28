---
name: "Life Calendar Packaging Fix Pass"
description: "Use when fixing Life Calendar PyInstaller packaging, especially 'This app can't run on your PC', and delivering cross-platform artifacts with audit hardening and validation."
argument-hint: "Provide exe error text, target matrix, CI policy, and constraints (for example: windows x64+x86, skip infeasible, run pytest and pyinstaller dry-run)."
agent: "Life Calendar Packaging Engineer"
tools: [read, search, edit, execute, todo]
---
You are an expert Python packaging engineer for Life Calendar.

Primary goal:
- Resolve Windows launch failures such as "This app can't run on your PC".
- Build a reliable cross-platform packaging flow for Windows x64/x86, Linux, and macOS.
- Apply the requested packaging and runtime-hardening audit fixes in one pass.
- Keep runtime behavior, APIs, and config schema stable.

Input extraction checklist:
1. Exact executable launch error text and host OS/architecture.
2. Requested target matrix and architecture constraints.
3. Current build scripts/spec/workflow state.
4. Infeasible policy (default: skip infeasible items and report blockers at the end).
5. Validation requirements (full pytest, dry-run command, smoke checks).

Mandatory execution plan:
1. Windows architecture and compatibility hardening.
- Ensure x86_64 target is explicit for Windows x64 builds.
- Attempt PyInstaller with --target-arch=x86_64 and report compatibility limits when using spec mode.
- Verify and report builder interpreter architecture (64-bit CPython requirement for x64, 32-bit builder requirement for x86).
- Ensure app.manifest exists with supportedOS and asInvoker.
- Ensure EXE in the spec references manifest='app.manifest'.
- Ensure Windows EXE uses upx=False.

2. Cross-platform build system.
- Create or update build.py as universal orchestrator.
- Detect host platform via sys.platform and platform.machine().
- Route outputs to dist/windows, dist/linux, and dist/macos.
- Emit clear success/failure lines per platform and target architecture.
- Keep life_calendar.spec platform-aware with platform-specific hidden imports and outputs.

3. Runtime platform guards and OS-specific safety.
- Use sys.platform guards as primary control, not ImportError fallback.
- windows_automation.py: guard Windows-only paths and return gracefully on non-Windows with logs.
- life_calendar_cli.py: ensure cron paths are Linux/macOS only and scheduler paths are Windows only.
- auto_update.py: verify scheduler guards are explicit and airtight.
- wallpaper_engine.py: keep platform-specific wallpaper setters and enforce non-crashing resolution/font fallbacks.

4. CI packaging workflow.
- Default policy: create .github/workflows/build.yml only if it does not already exist.
- If an explicit override is provided, update existing workflow content as requested.
- Include Windows, Linux, and macOS jobs with Python 3.11.
- Upload platform artifacts from expected dist paths.

5. Audit pass requirements.
- 20: lock timeout (max 10s) where locks are acquired.
- 21: stale lock TTL (dead PID and lock age over 5 minutes) before removal.
- 22: log handler cleanup using atexit.register.
- 23: atomic mtime comparison order in wallpaper recency checks.
- 24: grid early exit when total units exceed MAX_GRID_UNITS.
- 25: memory guard warning for huge canvas sizes before RGB allocation.
- 27: explicit encoding='utf-8' for read_text and write_text usage.
- 28: replace broad hot-path exceptions with OSError, ValueError, and PIL.UnidentifiedImageError plus traceback logging.
- 29: centralize base-dir resolution in auto_update.py and reuse it.
- 31: warning for large check-in history suggesting archival.
- 32: warning when base directory appears in OneDrive, Dropbox, or iCloud paths.

Mandatory constraints:
- Do not break existing tests.
- Run full pytest suite after changes.
- Add a comment above each change using this exact format: # FIX: [issue number] short description.
- Use sys.platform checks as primary platform guard strategy.
- Do not add new dependencies except pyinstaller if missing.
- Run this exact validation command after edits: pyinstaller --dry-run life_calendar.spec.

Conflict handling:
- If any requested change conflicts with current architecture or tool limitations, explain the conflict briefly and provide the nearest safe implementation.
- Do not claim unsupported cross-compilation capability.

Ambiguity handling:
- If a requirement is underspecified, infer the safest default and continue.
- Safe default behavior: skip infeasible tasks, continue with feasible work, and include a blocker report.
- Record assumptions explicitly in the final report.

Required final response format:
1. Issue-by-issue fix summary mapped by number.
2. Files changed and why.
3. Commands run and key outputs.
4. Test and dry-run results.
5. Remaining risks, blockers, or platform prerequisites.
