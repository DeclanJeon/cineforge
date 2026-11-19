"""Sound design plan and MCP lane routing; no audio is generated here."""
from pathlib import Path
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass

MCP_SERVERS = {
    'fish_audio': ('Voice design and TTS', ['fish-audio-mcp']),
    'typecast': ('Korean TTS via Cast', ['typecast-mcp']),
    'elevenlabs': ('Sound effects and music', ['elevenlabs-mcp']),
    'suno': ('BGM generation', ['suno-mcp']),
}
KEYS = {
    'fish_audio': 'FISH_AUDIO_API_KEY',
    'typecast': 'TYPECAST_API_KEY',
    'elevenlabs': 'ELEVENLABS_API_KEY',
    'suno': 'SUNO_API_KEY',
}
LANES = {
    'BGM': ('suno', 'suno_generate', True),
    'SFX': ('elevenlabs', 'elevenlabs_sound_effect', False),
    'AMBIENCE': ('elevenlabs', 'elevenlabs_sound_effect', True),
    'DIALOGUE': ('fish_audio', 'fish_audio_tts', False),
    'OST': ('suno', 'suno_generate', False),
}


class SoundError(ValueError):
    """The sound plan or its provider lane is not buildable."""


class SetupError(RuntimeError):
    """MCP setup or credential registration was refused."""


@dataclass(frozen=True, slots=True)
class Cue:
    cue_id: str
    kind: str
    start: float
    end: float
    provider: str
    tool: str
    loop: bool
    prompt: str
    vocal: bool
    role: str
    ai_disclosure: bool = True


def _seconds(value: float) -> str:
    return f'{value:.2f}s'


def plan(cues: list[dict[str, object]], *, mood: str, era: str) -> list[Cue]:
    """Turn SSOT cues into provider-addressed prompts."""
    rows: list[Cue] = []
    for raw in cues:
        kind = str(raw['type'])
        if kind not in LANES:
            raise SoundError(f'unsupported cue type: {kind}')
        provider, tool, loop = LANES[kind]
        description = str(raw['description'])
        span = f"{_seconds(float(raw['tc_in']))}~{_seconds(float(raw['tc_out']))}"
        if kind == 'OST':
            voice = ("Original Korean title song with vocals; melody recurs as the series theme."
                     if raw.get('vocal') else "Original instrumental main theme, no vocals.")
            prompt = (f"{voice} {era} drama. Story: {mood}. Cue: {description}. Length {span}. "
                      "Cleared for this project only; no existing song or lyric.")
        elif kind == 'BGM':
            prompt = (f"Instrumental background score, no vocals. {era} Korean drama. Scene mood: {mood}. "
                      f"Cue: {description}. Length {span}. Leave room for dialogue; no sudden stingers.")
        elif kind == 'DIALOGUE':
            prompt = f"Korean dialogue line, natural delivery, no music bed. {description}. Length {span}."
        else:
            prompt = (f"Sound effect only, no music. {description}. {era} texture. Length {span}. "
                      f"{'Seamless loop.' if loop else 'Single hit, clean tail.'}")
        rows.append(Cue(str(raw['cue_id']), kind, float(raw['tc_in']), float(raw['tc_out']), provider, tool, loop, prompt,
                        bool(raw.get('vocal')), str(raw.get('role') or kind.lower())))
    return rows


def write_plan(root: Path, cues: list[Cue], *, selected: dict[str, str]) -> dict[str, object]:
    payload = {'schema_version': 1, 'generated': False, 'cues': [
        {'cue_id': c.cue_id, 'kind': c.kind, 'tc_in': c.start, 'tc_out': c.end, 'provider': selected.get(c.provider, c.provider),
         'tool': c.tool, 'loop': c.loop, 'prompt': c.prompt, 'vocal': c.vocal, 'role': c.role,
         'ai_disclosure': c.ai_disclosure} for c in cues]}
    target = root / 'assets/sound_plan.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    return payload


def credentials_path() -> Path:
    base = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config')
    return base / 'cineforge' / 'credentials.json'


def set_key(provider: str, value: str, *, path: Path | None = None) -> Path:
    if provider not in KEYS:
        raise SetupError(f'unknown provider: {provider}')
    secret = value.strip()
    if len(secret) < 8 or re.search(r'\s', secret):
        raise SetupError('invalid key value')
    target = path or credentials_path()
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    current = json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}
    current[KEYS[provider]] = secret
    handle = tempfile.NamedTemporaryFile('w', dir=target.parent, delete=False, encoding='utf-8')
    try:
        json.dump(current, handle, ensure_ascii=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    finally:
        handle.close()
    os.chmod(handle.name, 0o600)
    os.replace(handle.name, target)
    return target


def remove_key(provider: str, *, path: Path | None = None) -> Path:
    if provider not in KEYS:
        raise SetupError(f'unknown provider: {provider}')
    target = path or credentials_path()
    current = json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}
    current.pop(KEYS[provider], None)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    target.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding='utf-8')
    os.chmod(target, 0o600)
    return target


def status(*, path: Path | None = None) -> list[dict[str, object]]:
    target = path or credentials_path()
    stored = json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}
    return [{'server': name, 'purpose': purpose, 'commands': commands,
             'command_available': any(shutil.which(command) for command in commands),
             'key_env': KEYS[name], 'key_registered': bool(stored.get(KEYS[name]) or os.environ.get(KEYS[name]))}
            for name, (purpose, commands) in MCP_SERVERS.items()]


def apply(selected: list[str], *, yes: bool, runner=None, recipes: dict[str, list[str]] | None = None) -> list[str]:
    """Run the caller-declared install recipes. No invented package names."""
    unknown = [name for name in selected if name not in MCP_SERVERS]
    if unknown:
        raise SetupError(f'unknown server: {", ".join(unknown)}')
    if not selected:
        raise SetupError('no server selected')
    if not yes:
        raise SetupError('confirmation_required')
    declared = recipes or {}
    missing = [name for name in selected if not declared.get(name)]
    if missing:
        raise SetupError(f"install_recipe_unknown: {', '.join(missing)} — 서버별 설치 명령을 지정하세요")
    run = runner or (lambda command: subprocess.run(command, check=True, capture_output=True, text=True))
    done = []
    for name in selected:
        try:
            run(list(declared[name]))
        except (OSError, subprocess.SubprocessError) as exc:
            raise SetupError(f'install_failed: {name}: {exc}') from exc
        done.append(name)
    return done


def agent_config(host: str) -> dict[str, object]:
    if host not in ('codex', 'claude', 'pi'):
        raise SetupError(f'unsupported host: {host}')
    return {'host': host, 'servers': {name: {'command': commands[0], 'env': KEYS[name]} for name, (_, commands) in MCP_SERVERS.items()}}
