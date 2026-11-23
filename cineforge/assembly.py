"""Deterministic local assembly: trim adopted takes, mix cue audio, normalise loudness."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
from typing import Any


class AssemblyError(RuntimeError):
    """ffmpeg could not assemble the approved plan."""


def _tool(name: str) -> str:
    found = shutil.which(name)
    if not found:
        raise AssemblyError(f'tool_missing: {name}')
    return found


def render(project: Path, plan: dict[str, Any], *, output: str = 'edit/render.mp4',
           size: tuple[int, int] | None = None) -> Path:
    from .project_skills import require_pack

    require_pack(project)
    ffmpeg = _tool('ffmpeg')
    width, height = size or (int(plan['width']), int(plan['height']))
    fps = int(plan.get('fps', 24))
    runtime = float(plan['runtime'])
    target = project / output
    target.parent.mkdir(parents=True, exist_ok=True)
    inputs: list[str] = []
    filters: list[str] = []
    for index, cut in enumerate(plan['cuts']):
        source = project / cut['path']
        if not source.is_file():
            raise AssemblyError(f"cut_missing: {cut['cut_id']}")
        inputs += ['-i', str(source)]
        filters.append(
            f"[{index}:v]trim=0:{float(cut['out']) - float(cut['in']):.3f},setpts=PTS-STARTPTS,fps={fps},"
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1[v{index}]")
    joins = ''.join(f'[v{index}]' for index in range(len(plan['cuts'])))
    filters.append(f'{joins}concat=n={len(plan["cuts"])}:v=1:a=0[vout]')
    audio_count = len(plan['audio'])
    if audio_count:
        for offset, cue in enumerate(plan['audio']):
            index = len(plan['cuts']) + offset
            inputs += ['-i', str(project / cue['path'])]
            delay = int(round(float(cue['in']) * 1000))
            length = max(0.05, float(cue['out']) - float(cue['in']))
            filters.append(
                f"[{index}:a]atrim=0:{length:.3f},asetpts=PTS-STARTPTS,volume={cue['gain_db']}dB,"
                f"adelay={delay}|{delay},apad,atrim=0:{runtime:.3f}[a{offset}]")
        mix = ''.join(f'[a{index}]' for index in range(audio_count))
        filters.append(f"{mix}amix=inputs={audio_count}:duration=longest:normalize=0,"
                       f"loudnorm=I=-14:TP=-1:LRA=11[aout]")
    else:
        inputs += ['-f', 'lavfi', '-t', f'{runtime:.3f}', '-i', 'anullsrc=channel_layout=stereo:sample_rate=48000']
        filters.append(f'[{len(plan["cuts"])}:a]atrim=0:{runtime:.3f},asetpts=PTS-STARTPTS[aout]')
    command = [ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', *inputs,
               '-filter_complex', ';'.join(filters), '-map', '[vout]', '-map', '[aout]',
               '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', '-r', str(fps),
               '-c:a', 'aac', '-b:a', '128k', '-ar', '48000', '-movflags', '+faststart', str(target)]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise AssemblyError(f'ffmpeg_failed: {result.stderr.strip()[:300]}')
    _normalize(target)
    return target


def _normalize(target: Path) -> None:
    """Close the gap single-pass loudnorm leaves; video is stream-copied, at most twice."""
    for _ in range(2):
        measured = loudness(target)
        delta = -14.0 - measured['integrated']
        if abs(delta) < 0.6:
            return
        temporary = target.with_name(target.stem + '-norm' + target.suffix)
        command = [_tool('ffmpeg'), '-hide_banner', '-loglevel', 'error', '-y', '-i', str(target), '-c:v', 'copy',
                   '-af', f'volume={delta:.2f}dB,alimiter=level_in=1:limit=0.891', '-c:a', 'aac', '-b:a', '128k',
                   '-ar', '48000', '-movflags', '+faststart', str(temporary)]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            raise AssemblyError(f'normalize_failed: {result.stderr.strip()[:200]}')
        temporary.replace(target)


def probe(path: Path) -> dict[str, Any]:
    result = subprocess.run([_tool('ffprobe'), '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)],
                            check=True, capture_output=True, text=True)
    document = json.loads(result.stdout)
    video = next((row for row in document['streams'] if row['codec_type'] == 'video'), {})
    audio = next((row for row in document['streams'] if row['codec_type'] == 'audio'), {})
    return {'duration': float(document['format']['duration']), 'width': int(video.get('width', 0)),
            'height': int(video.get('height', 0)), 'video_codec': video.get('codec_name'),
            'audio_codec': audio.get('codec_name'), 'fps': video.get('r_frame_rate')}


def loudness(path: Path) -> dict[str, float]:
    result = subprocess.run([_tool('ffmpeg'), '-hide_banner', '-nostats', '-i', str(path),
                             '-af', 'loudnorm=print_format=json', '-f', 'null', '-'],
                            capture_output=True, text=True)
    payload = result.stderr[result.stderr.rindex('{'):result.stderr.rindex('}') + 1]
    document = json.loads(payload)
    return {'integrated': float(document['input_i']), 'true_peak': float(document['input_tp'])}
