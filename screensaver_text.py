#!/usr/bin/env python3
"""Save Omarchy screensaver text and show the updated screensaver."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def read_current_text(config: Path, branding: Path, default_logo: Path) -> str:
    if branding.exists() and default_logo.exists() and branding.read_bytes() == default_logo.read_bytes():
        return "Omarchy"
    if config.exists():
        return str(json.loads(config.read_text(encoding="utf-8")).get("text", ""))
    return ""


def read_timeouts(shell_config: Path) -> tuple[int, int]:
    settings = json.loads(shell_config.read_text(encoding="utf-8"))
    if not isinstance(settings, dict) or settings.get("version") != 1:
        raise ValueError("Invalid Omarchy shell config")
    idle = settings.get("idle", {})
    if not isinstance(idle, dict):
        raise ValueError("Invalid Omarchy idle config")
    return int(idle.get("screensaver", 150)), int(idle.get("lock", 300))


def update_timeout(shell_config: Path, seconds: int) -> None:
    settings = json.loads(shell_config.read_text(encoding="utf-8"))
    if not isinstance(settings, dict) or settings.get("version") != 1:
        raise ValueError("Invalid Omarchy shell config")
    idle = settings.get("idle")
    if not isinstance(idle, dict):
        raise ValueError("Invalid Omarchy idle config")
    idle["screensaver"] = seconds
    # Atomic replacement so the shell watcher never reads partial JSON.
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=shell_config.parent,
                                     prefix=".shell-", delete=False) as output:
        temporary = Path(output.name)
        json.dump(settings, output, ensure_ascii=False, indent=2)
        output.write("\n")
    try:
        os.chmod(temporary, shell_config.stat().st_mode & 0o777)
        temporary.replace(shell_config)
    finally:
        temporary.unlink(missing_ok=True)


def schedule_shell_restart() -> None:
    # Quickshell's existing IdleMonitor does not re-register for timeout changes.
    # Delay the restart so the action can return to its owning shell UI first.
    omarchy = shutil.which("omarchy")
    if not omarchy:
        raise OSError("omarchy command not found")
    subprocess.run(["systemd-run", "--user", "--collect", "--on-active=2s",
                    omarchy, "restart", "shell"], check=True)


def save(text: str, config: Path, branding: Path, shell_config: Path,
         seconds_text: str, *, launch: bool = True) -> None:
    text = text.strip()
    if not text:
        raise ValueError("Enter some screensaver text before saving")
    if "\n" in text or "\r" in text:
        raise ValueError("Screensaver text must be a single line")
    if not seconds_text.isascii() or not seconds_text.isdecimal():
        raise ValueError("Seconds must contain only digits")
    seconds = int(seconds_text)
    previous_seconds, lock_seconds = read_timeouts(shell_config)
    if not 1 <= seconds <= 86400:
        raise ValueError("Seconds must be between 1 and 86400")
    if seconds >= lock_seconds:
        raise ValueError("Screensaver must start before the lock timeout")

    # Send text via stdin, not a shell command or a figlet option.
    artwork = subprocess.run(
        ["figlet", "-f", "ansi-regular"],
        input=text + "\n",
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    config.parent.mkdir(parents=True, exist_ok=True)
    branding.parent.mkdir(parents=True, exist_ok=True)
    branding.write_text(artwork, encoding="utf-8")
    config.write_text(json.dumps({"text": text}, ensure_ascii=False) + "\n", encoding="utf-8")
    update_timeout(shell_config, seconds)
    if launch:
        if seconds != previous_seconds:
            schedule_shell_restart()
        subprocess.run(["omarchy-launch-screensaver", "force"], check=True)


def restore_default(config: Path, shell_config: Path) -> None:
    # Restore the stock logo, then reset only the screensaver idle timeout.
    subprocess.run(["omarchy", "branding", "screensaver", "reset"], check=True)
    previous_seconds, _ = read_timeouts(shell_config)
    if previous_seconds != 150:
        update_timeout(shell_config, 150)
    # Old figlet input no longer represents the logo; do not prefill it on reopen.
    config.unlink(missing_ok=True)
    if previous_seconds != 150:
        schedule_shell_restart()


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print("Usage: screensaver_text.py TEXT SECONDS|--restore|--read-text|--read-timeouts", file=sys.stderr)
        return 2
    home = Path.home()
    config_dir = home / ".config/omarchy"
    shell_config = config_dir / "shell.json"
    try:
        if sys.argv[1] == "--restore" and len(sys.argv) == 2:
            restore_default(config_dir / "screensaver-text.json", shell_config)
        elif sys.argv[1] == "--read-text" and len(sys.argv) == 2:
            logo = Path(os.environ.get("OMARCHY_PATH", "/usr/share/omarchy")) / "logo.txt"
            print(read_current_text(config_dir / "screensaver-text.json",
                                    config_dir / "branding/screensaver.txt", logo))
        elif sys.argv[1] == "--read-timeouts" and len(sys.argv) == 2:
            screensaver, lock = read_timeouts(shell_config)
            print(json.dumps({"screensaver": screensaver, "lock": lock}))
        elif len(sys.argv) == 3:
            save(
                sys.argv[1],
                config_dir / "screensaver-text.json",
                config_dir / "branding/screensaver.txt",
                shell_config,
                sys.argv[2],
            )
        else:
            raise ValueError("Specify both text and seconds")
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"Screensaver change failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
