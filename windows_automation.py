"""Windows Task Scheduler helpers for Life Calendar automation."""

from __future__ import annotations

from datetime import datetime
import logging
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Optional
from xml.sax.saxutils import escape

from auto_update import get_base_dir as shared_get_base_dir

WALLPAPER_TASK_NAME = "LifeCalendarWallpaper"
STARTUP_TASK_NAME = "LifeCalendarStartupPrompt"
logger = logging.getLogger("windows_automation")


def sync_windows_tasks(config: dict, base_dir: Optional[str | Path] = None) -> tuple[bool, list[str]]:
    """Create or remove Windows tasks so they match config preferences."""
    # FIX: [29] Use explicit sys.platform guards for platform-specific automation.
    if sys.platform != "win32":
        logger.info("Skipping Windows task sync on non-Windows platform: %s", sys.platform)
        return True, []

    automation = config.get("automation", {}) if isinstance(config, dict) else {}
    wallpaper_enabled = bool(automation.get("wallpaper_refresh_enabled", True))
    startup_enabled = bool(automation.get("startup_enabled", True))
    errors: list[str] = []

    if wallpaper_enabled:
        success, error = create_wallpaper_task(base_dir)
        if not success and error:
            errors.append(error)
    elif not remove_windows_task(WALLPAPER_TASK_NAME):
        errors.append(f"Could not remove {WALLPAPER_TASK_NAME}.")

    if startup_enabled:
        success, error = create_startup_task(base_dir)
        if not success and error:
            errors.append(error)
    elif not remove_windows_task(STARTUP_TASK_NAME):
        errors.append(f"Could not remove {STARTUP_TASK_NAME}.")

    # Preserve order while removing duplicate messages (common with permission errors).
    deduped_errors = list(dict.fromkeys(errors))
    return not deduped_errors, deduped_errors


def create_wallpaper_task(base_dir: Optional[str | Path] = None) -> tuple[bool, Optional[str]]:
    """Create or update the midnight plus resume wallpaper refresh task."""
    command, arguments, working_dir = resolve_task_action("--headless-update", base_dir)
    start_boundary = datetime.now().strftime("%Y-%m-%dT00:01:00")
    xml_content = build_wallpaper_task_xml(command, arguments, working_dir, start_boundary)
    return _create_task_from_xml(WALLPAPER_TASK_NAME, xml_content)


def create_startup_task(base_dir: Optional[str | Path] = None) -> tuple[bool, Optional[str]]:
    """Create or update the logon reminder task."""
    command, arguments, working_dir = resolve_task_action("--startup-check", base_dir)
    xml_content = build_startup_task_xml(command, arguments, working_dir)
    return _create_task_from_xml(STARTUP_TASK_NAME, xml_content)


def remove_windows_task(task_name: str) -> bool:
    """Remove a scheduled task. Missing tasks are treated as success."""
    # FIX: [29] Use explicit sys.platform guards for platform-specific automation.
    if sys.platform != "win32":
        logger.info("Skipping task removal on non-Windows platform: %s", task_name)
        return True

    query = subprocess.run(
        ["schtasks", "/Query", "/TN", task_name],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if query.returncode != 0:
        return True

    delete = subprocess.run(
        ["schtasks", "/Delete", "/TN", task_name, "/F"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    return delete.returncode == 0


def resolve_task_action(mode_flag: str, base_dir: Optional[str | Path] = None) -> tuple[str, str, str]:
    """Resolve the command, arguments, and working directory for a task action."""
    # FIX: [29] Reuse centralized base-dir resolution.
    target_dir = Path(base_dir) if base_dir else shared_get_base_dir()

    if getattr(sys, "frozen", False):
        # Frozen exe - quote the exe path and arguments to handle spaces
        exe_path = str(Path(sys.executable))
        command = f'"{exe_path}"'
        arguments = f'"{mode_flag}"'
        working_dir = str(Path(sys.executable).resolve().parent)
    else:
        # Python script - quote both the interpreter and script path
        script_path = target_dir / "life_calendar_gui.py"
        command = sys.executable
        arguments = f'"{script_path}" {mode_flag}'
        working_dir = str(target_dir)

    return command, arguments, working_dir


def build_wallpaper_task_xml(command: str, arguments: str, working_dir: str, start_boundary: str) -> str:
    """Build XML for the wallpaper refresh task."""
    return _build_task_xml(
        triggers="""
    <CalendarTrigger>
      <StartBoundary>{start_boundary}</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByDay>
        <DaysInterval>1</DaysInterval>
      </ScheduleByDay>
    </CalendarTrigger>
    <BootTrigger>
      <Enabled>true</Enabled>
      <Delay>PT60S</Delay>
    </BootTrigger>
    <SessionStateChangeTrigger>
      <Enabled>true</Enabled>
      <Delay>PT10S</Delay>
      <StateChange>SessionUnlock</StateChange>
    </SessionStateChangeTrigger>
""".format(start_boundary=escape(start_boundary)),
        command=command,
        arguments=arguments,
        working_dir=working_dir,
        description="Life Calendar wallpaper refresh",
    )


def build_startup_task_xml(command: str, arguments: str, working_dir: str) -> str:
    """Build XML for the startup prompt task."""
    return _build_task_xml(
        triggers="""
    <LogonTrigger>
      <Enabled>true</Enabled>
      <Delay>PT45S</Delay>
    </LogonTrigger>
""",
        command=command,
        arguments=arguments,
        working_dir=working_dir,
        description="Life Calendar daily startup prompt",
    )


def _build_task_xml(triggers: str, command: str, arguments: str, working_dir: str, description: str) -> str:
    command_xml = escape(command)
    arguments_xml = escape(arguments)
    working_dir_xml = escape(working_dir)
    description_xml = escape(description)
    arguments_block = f"      <Arguments>{arguments_xml}</Arguments>\n" if arguments else ""

    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>{description_xml}</Description>
  </RegistrationInfo>
  <Triggers>
{triggers.rstrip()}
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <ExecutionTimeLimit>PT5M</ExecutionTimeLimit>
    <AllowHardTerminate>true</AllowHardTerminate>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <WakeToRun>false</WakeToRun>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{command_xml}</Command>
{arguments_block}      <WorkingDirectory>{working_dir_xml}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""


def _create_task_from_xml(task_name: str, xml_content: str) -> tuple[bool, Optional[str]]:
    """Create or update a scheduled task from an XML definition."""
    # FIX: [29] Use explicit sys.platform guards for platform-specific automation.
    if sys.platform != "win32":
        logger.info("Skipping task creation on non-Windows platform: %s", task_name)
        return True, None

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as temp_file:
            temp_path = temp_file.name
            temp_file.write(xml_content.encode("utf-16"))

        result = subprocess.run(
            ["schtasks", "/Create", "/TN", task_name, "/XML", temp_path, "/F"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            return True, None

        message = result.stderr.strip() or result.stdout.strip() or f"Unknown error creating {task_name}"

        lower_message = message.lower()
        if "access is denied" in lower_message or "0x80070005" in lower_message:
            return (
                False,
                (
                    f"Access denied while creating '{task_name}'. "
                    "Run Life Calendar as Administrator and retry automation setup."
                ),
            )

        return False, f"Could not create '{task_name}': {message}"
    except Exception as exc:
        return False, str(exc)
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass
