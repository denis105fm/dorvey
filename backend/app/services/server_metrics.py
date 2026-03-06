"""Collect VPS metrics via SSH (load, memory, disk)."""

import re
from typing import Optional

from app.models.server import Server
from app.services.deploy import _get_ssh_client, _get_ssh_client_from_params


def _run_command(client, command: str, timeout: int = 15) -> tuple[bool, str]:
    try:
        _, stdout, stderr = client.exec_command(command, timeout=timeout)
        out = (stdout.read() or b"").decode("utf-8", errors="replace")
        err = (stderr.read() or b"").decode("utf-8", errors="replace")
        if err and not out:
            return False, err.strip() or "Empty output"
        return True, out.strip()
    except Exception as e:
        return False, str(e)


def _parse_metrics_output(out: str) -> Optional[dict]:
    data = {}
    section = None
    for line in out.splitlines():
        line = line.strip()
        if line == "---LOAD---":
            section = "load"
            continue
        if line == "---MEM---":
            section = "mem"
            continue
        if line == "---DISK---":
            section = "disk"
            continue
        if line == "---NPROC---":
            section = "nproc"
            continue
        if section == "load" and line:
            parts = line.split()
            if len(parts) >= 3:
                try:
                    data["load_1"] = float(parts[0])
                    data["load_5"] = float(parts[1])
                    data["load_15"] = float(parts[2])
                except ValueError:
                    pass
            section = None
        if section == "mem" and line:
            m = re.match(r"^(MemTotal|MemAvailable):\s*(\d+)\s*kB", line)
            if m:
                data["mem_total_kb" if m.group(1) == "MemTotal" else "mem_available_kb"] = int(m.group(2))
        if section == "disk" and line:
            parts = line.split()
            if len(parts) >= 3:
                try:
                    data["disk_total_kb"] = int(parts[1])
                    data["disk_used_kb"] = int(parts[2])
                except ValueError:
                    pass
            section = None
        if section == "nproc" and line:
            try:
                data["nproc"] = int(line.strip())
            except ValueError:
                data["nproc"] = 1
            section = None
    if "load_1" in data and "mem_total_kb" in data and "disk_total_kb" in data:
        data.setdefault("mem_available_kb", 0)
        data.setdefault("nproc", 1)
        return data
    return None


def _metrics_cmd() -> str:
    return (
        "echo '---LOAD---' && cat /proc/loadavg 2>/dev/null; "
        "echo '---MEM---' && grep -E '^MemTotal:|^MemAvailable:' /proc/meminfo 2>/dev/null; "
        "echo '---DISK---' && df -k / 2>/dev/null | tail -1; "
        "echo '---NPROC---' && nproc 2>/dev/null || echo 1"
    )


def _run_remote(server: Server, command: str, timeout: int = 15) -> tuple[bool, str]:
    """Run command over SSH, return (success, stdout or error)."""
    try:
        client = _get_ssh_client(server)
        try:
            return _run_command(client, command, timeout=timeout)
        finally:
            client.close()
    except Exception as e:
        return False, str(e)


def collect_metrics(server: Server) -> Optional[dict]:
    """
    Collect load, memory, disk from server via SSH.
    Returns dict with keys: load_1, load_5, load_15, mem_total_kb, mem_available_kb,
    disk_total_kb, disk_used_kb, nproc (CPU count). On error returns None.
    """
    cmd = _metrics_cmd()
    try:
        client = _get_ssh_client(server)
        try:
            ok, out = _run_command(client, cmd)
            if not ok or not out:
                return None
            return _parse_metrics_output(out)
        finally:
            client.close()
    except Exception:
        return None


def collect_metrics_from_params(
    host: str,
    port: int,
    user: str,
    auth_type: str,
    auth_data: Optional[str],
) -> Optional[dict]:
    """Collect metrics using raw SSH params (for Celery/thread)."""
    cmd = _metrics_cmd()
    try:
        client = _get_ssh_client_from_params(host, port, user, auth_type, auth_data)
        try:
            ok, out = _run_command(client, cmd)
            if not ok or not out:
                return None
            return _parse_metrics_output(out)
        finally:
            client.close()
    except Exception:
        return None
