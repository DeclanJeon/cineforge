"""Read MCP servers that other agents already installed; never modify them.

CineForge does not launch MCP servers, but it should not ask for a second
install of something Codex/Claude/Gemini already has. Discovery is read-only:
commands, URLs and environment *names* are copied, never secret values.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - 3.10 fallback
    tomllib = None  # type: ignore[assignment]

ALIASES = {
    'fish_audio': ('fish_audio', 'fish-audio', 'fish', 'fishaudio'),
    'typecast': ('typecast',),
    'elevenlabs': ('elevenlabs', '11labs', 'eleven_labs'),
    'suno': ('suno',),
    'ludyte': ('ludyte',),
}
JSON_KEYS = ('mcpServers', 'mcp_servers', 'servers')
def config_path() -> Path:
    return Path.home() / '.config/cineforge/mcp.json'


def candidates(home: Path | None = None) -> list[tuple[str, Path]]:
    base = home or Path.home()
    return [
        ('codex', base / '.codex/config.toml'),
        ('claude', base / '.claude.json'),
        ('claude', base / '.config/Claude/claude_desktop_config.json'),
        ('gemini', base / '.gemini/settings.json'),
        ('opencode', base / '.config/opencode/opencode.json'),
        ('opencode', base / '.config/opencode/opencode.jsonc'),
        ('pi', base / '.pi/agent/mcp.json'),
        ('mcp', base / '.config/mcp/mcp.json'),
    ]


def _entry(agent: str, source: Path, name: str, spec: dict[str, Any]) -> dict[str, Any]:
    return {'agent': agent, 'source': str(source), 'name': name,
            'command': spec.get('command'), 'args': spec.get('args') or [],
            'url': spec.get('url') or spec.get('httpUrl') or spec.get('endpoint'),
            'env_keys': sorted((spec.get('env') or {}).keys())}


def strip_jsonc(text: str) -> str:
    """Remove // and /* */ comments and trailing commas outside strings (opencode.jsonc)."""
    out, i, n, in_str = [], 0, len(text), False
    while i < n:
        ch = text[i]
        if in_str:
            out.append(ch)
            if ch == '\\' and i + 1 < n:
                out.append(text[i + 1]); i += 2; continue
            if ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True; out.append(ch)
        elif text.startswith('//', i):
            while i < n and text[i] != '\n':
                i += 1
            continue
        elif text.startswith('/*', i):
            end = text.find('*/', i + 2)
            i = n if end < 0 else end + 2
            continue
        else:
            out.append(ch)
        i += 1
    import re
    return re.sub(r',(\s*[}\]])', r'\1', ''.join(out))


def _from_json(agent: str, path: Path) -> list[dict[str, Any]]:
    try:
        raw = path.read_text(encoding='utf-8')
        document = json.loads(strip_jsonc(raw) if path.suffix == '.jsonc' else raw)
    except (OSError, ValueError):
        return []
    servers: Any = None
    for key in JSON_KEYS:
        if isinstance(document, dict) and isinstance(document.get(key), dict):
            servers = document[key]
            break
    if servers is None and isinstance(document, dict) and isinstance(document.get('mcp'), dict):
        mcp = document['mcp']
        # opencode keeps {name: spec} directly under "mcp"; others nest under "servers".
        servers = mcp.get('servers') if isinstance(mcp.get('servers'), dict) else {
            k: v for k, v in mcp.items() if isinstance(v, dict) and any(key in v for key in ('url', 'command', 'type'))}
    if not isinstance(servers, dict):
        return []
    return [_entry(agent, path, str(name), spec if isinstance(spec, dict) else {})
            for name, spec in servers.items()]


def _from_toml(agent: str, path: Path) -> list[dict[str, Any]]:
    if tomllib is None:
        return []
    try:
        document = tomllib.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []
    servers = document.get('mcp_servers')
    if not isinstance(servers, dict):
        return []
    rows = []
    for name, spec in servers.items():
        if not isinstance(spec, dict):
            continue
        if any(key in spec for key in ('command', 'url', 'endpoint')):
            rows.append(_entry(agent, path, str(name), spec))
    return rows


def discover(home: Path | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for agent, path in candidates(home):
        if not path.is_file():
            continue
        rows.extend(_from_toml(agent, path) if path.suffix == '.toml' else _from_json(agent, path))
    return rows


def provider_of(name: str) -> str | None:
    lowered = name.lower()
    for provider, names in ALIASES.items():
        if lowered in names:
            return provider
    return None


def matches(rows: list[dict[str, Any]] | None = None) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for row in rows if rows is not None else discover():
        provider = provider_of(str(row['name']))
        if provider and provider not in found:
            found[provider] = row
    return found


def _provider_rows(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        provider = provider_of(str(row['name']))
        if provider:
            grouped.setdefault(provider, []).append(row)
    return grouped


def sync(rows: list[dict[str, Any]] | None = None, *, target: Path | None = None) -> dict[str, Any]:
    """Refresh the imported cache from the live host scan; never touch host configs."""
    path = target or config_path()
    grouped = _provider_rows(rows if rows is not None else discover())
    previous = imported(path=path).get('providers', {})
    providers: dict[str, Any] = {}
    conflicts: list[dict[str, Any]] = []
    added, updated, removed = [], [], []
    for provider, candidates in sorted(grouped.items()):
        # Prefer the entry that names its environment variables: it carries the
        # credential contract the other client already solved.
        chosen = sorted(candidates, key=lambda row: -len(row.get('env_keys') or []))[0]
        if len(candidates) > 1:
            conflicts.append({'provider': provider, 'chosen': chosen['source'],
                              'alternatives': sorted({row['source'] for row in candidates if row is not chosen})})
        entry = {key: chosen.get(key) for key in ('agent', 'source', 'name', 'command', 'args', 'url', 'env_keys')}
        if provider not in previous:
            added.append(provider)
        elif previous[provider].get('source') != entry['source'] or previous[provider].get('command') != entry['command'] \
                or previous[provider].get('args') != entry['args'] or previous[provider].get('url') != entry['url']:
            updated.append(provider)
        providers[provider] = entry
    removed = sorted(set(previous) - set(providers))
    payload = {'schema_version': 1, 'imported_from': 'read-only host scan',
               'providers': providers, 'conflicts': conflicts}
    changed = providers != previous or conflicts != imported(path=path).get('conflicts', [])
    if changed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        os.chmod(path, 0o600)
    return {'target': str(path), 'added': added, 'updated': updated, 'removed': removed,
            'conflicts': conflicts, 'changed': changed}


def import_config(rows: list[dict[str, Any]] | None = None, *, target: Path | None = None) -> Path:
    result = sync(rows, target=target)
    return Path(result['target'])


def imported(*, path: Path | None = None) -> dict[str, Any]:
    target = path or config_path()
    if not target.is_file():
        return {'providers': {}}
    return json.loads(target.read_text(encoding='utf-8'))
