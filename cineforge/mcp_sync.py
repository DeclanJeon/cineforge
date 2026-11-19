"""Background MCP sync: watch other agents' configs and refresh CineForge's cache.

The daemon never writes outside ~/.config/cineforge, never copies secret values
and never touches another agent's configuration. It exists only to keep the
imported cache current between explicit `cineforge setup` runs.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
from typing import Any

from .mcp_discovery import sync

LOCK_MARK = 'cineforge.mcp_sync'


def config_dir() -> Path:
    return Path.home() / '.config/cineforge'


def state_path() -> Path:
    return config_dir() / 'mcp-sync.json'


def log_path() -> Path:
    return config_dir() / 'mcp-sync.log'


def _read_state() -> dict[str, Any]:
    path = state_path()
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except ValueError:
        return {}


def _write_state(payload: dict[str, Any]) -> None:
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def _alive(pid: int) -> bool:
    try:
        cmdline = Path(f'/proc/{pid}/cmdline').read_bytes().decode('utf-8', 'ignore')
    except OSError:
        return False
    return LOCK_MARK in cmdline


def running() -> dict[str, Any] | None:
    state = _read_state()
    pid = state.get('pid')
    if isinstance(pid, int) and pid > 0 and _alive(pid):
        return state
    return None


def _log(message: str) -> None:
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as stream:
        stream.write(f'{time.strftime("%Y-%m-%dT%H:%M:%S")} {message}\n')


def loop(interval: float = 5.0) -> int:
    stop = threading.Event()

    def handle(_signum: int, _frame: object) -> None:
        stop.set()

    signal.signal(signal.SIGTERM, handle)
    signal.signal(signal.SIGINT, handle)
    _write_state({'pid': os.getpid(), 'started_at': int(time.time()), 'interval': interval,
                  'last_run': None, 'last_result': None})
    _log(f'started pid={os.getpid()} interval={interval}')
    try:
        while not stop.is_set():
            try:
                report = sync()
                _write_state({'pid': os.getpid(), 'started_at': int(time.time()), 'interval': interval,
                              'last_run': int(time.time()), 'last_result': {key: report[key] for key in
                                                                             ('added', 'updated', 'removed', 'conflicts', 'changed')}})
                if report['changed']:
                    _log(f"synced added={report['added']} updated={report['updated']} removed={report['removed']}")
            except Exception as exc:  # noqa: BLE001 - a watcher must not die on one bad file
                _log(f'error {type(exc).__name__}: {exc}')
            stop.wait(interval)
    finally:
        state = _read_state()
        if state.get('pid') == os.getpid():
            state_path().unlink(missing_ok=True)
        _log(f'stopped pid={os.getpid()}')
    return 0


def start(*, interval: float = 5.0) -> dict[str, Any]:
    current = running()
    if current:
        return {'status': 'already_running', **current}
    config_dir().mkdir(parents=True, exist_ok=True)
    log = log_path().open('ab')
    process = subprocess.Popen([sys.executable, '-B', '-m', 'cineforge.mcp_sync', '--interval', str(interval)],
                               stdout=log, stderr=log, stdin=subprocess.DEVNULL, start_new_session=True)
    for _ in range(50):
        time.sleep(0.05)
        state = _read_state()
        if state.get('pid') == process.pid:
            return {'status': 'started', 'pid': process.pid, 'interval': interval, 'log': str(log_path())}
    return {'status': 'start_failed', 'pid': process.pid}


def stop(*, timeout: float = 3.0) -> dict[str, Any]:
    current = running()
    if not current:
        return {'status': 'not_running'}
    pid = int(current['pid'])
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        state_path().unlink(missing_ok=True)
        return {'status': 'stale_state_cleared'}
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not _alive(pid):
            return {'status': 'stopped', 'pid': pid}
        time.sleep(0.05)
    return {'status': 'stop_timeout', 'pid': pid}


def status() -> dict[str, Any]:
    current = running()
    state = _read_state()
    log = log_path()
    tail = ''
    if log.is_file():
        tail = '\n'.join(log.read_text(encoding='utf-8', errors='ignore').splitlines()[-5:])
    return {'running': current is not None, **(current or {'pid': None}), 'last_run': state.get('last_run'),
            'last_result': state.get('last_result'), 'log': str(log), 'log_tail': tail}


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(prog='cineforge.mcp_sync')
    parser.add_argument('--interval', type=float, default=5.0)
    args = parser.parse_args()
    raise SystemExit(loop(args.interval))
