"""Shared fixture: a prepared mock project with generated image placeholders."""
from pathlib import Path

from cineforge.cli import main
from cineforge.pipeline import Project
from conftest import SAMPLE_REQUEST

PNG = b'\x89PNG\r\n\x1a\n' + b'closure'


def prepared(tmp_path: Path, request: str = SAMPLE_REQUEST, *, extra: list[str] | None = None) -> Project:
    args = ['new', request, '--projects-dir', str(tmp_path), '--project-id', 'p', '--provider', 'mock',
            '--no-nonstop', '--until', 'S03_plan', *(extra or [])]
    main(args)
    project = Project(tmp_path / 'p')
    project.grant(accept_plan=True, accept_preproduction=True)
    project.run(until='S07_assets')
    rows = project.read('assets/asset_registry.json')
    for row in rows['assets']:
        out = project.root / 'assets/generated' / (row['asset_id'] + '.png')
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(PNG + row['asset_id'].encode())
        row.update(status='available', path=f'assets/generated/{row["asset_id"]}.png', version=1)
    project.write('assets/asset_registry.json', rows, 'asset_registry')
    outputs = {}
    for row in project.read('assets/video_prompts.json')['prompts']:
        for ref in row['refs']:
            out = project.root / 'assets/generated' / (ref + '.png')
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(PNG + ref.encode())
            outputs[ref] = f'assets/generated/{ref}.png'
    project.write('assets/image_outputs.json', outputs)
    return project
