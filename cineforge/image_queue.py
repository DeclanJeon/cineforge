"""Supervise bounded Codex Imagen child sessions. No automatic retry of uncertain jobs."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
from functools import partial

from .receipts import atomic_text


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def codex_imagen(row, refs, output, *, supervisor_fd=None):
    node = shutil.which("node")
    helper = Path.home()/".codex/skills/codex-imagen/scripts/codex-imagen.mjs"
    if not node or not helper.is_file():
        raise ValueError("codex-imagen helper or node unavailable")
    args = [node, str(helper), "--no-retry", "--timeout", "300", "--output", str(output)]
    for ref in refs:
        args.extend(["--image", str(ref)])
    args.extend(["--prompt", f"Generate exactly one image. {row['prompt']} Aspect: {row.get('params', {}).get('aspect','')}. Avoid: {row.get('negative','')}"])
    with output.with_suffix(".log").open("ab") as log:
        subprocess.run(args, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                       start_new_session=True, pass_fds=(() if supervisor_fd is None else (supervisor_fd,)), timeout=330, check=True)


def generate(root, rows, limit, execute=None, supplied=None):
    import fcntl
    supplied = supplied or {}
    root = Path(root).resolve()
    directory = root/"assets"/"image_jobs"
    directory.mkdir(parents=True,exist_ok=True)
    jobs = {r["prompt_id"]:r for r in rows}
    if (len(jobs)!=len(rows) or not set(supplied)<=jobs.keys() or
            any(not re.fullmatch(r"[A-Za-z0-9_-]+", k) or not set(r["refs"])<=jobs.keys() for k,r in jobs.items())):
        raise ValueError("invalid image graph")
    # Serialize supervisors for this user. Five slots total, not five per project.
    lock_dir = Path.home()/".cache"/"cineforge"
    lock_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
    with (lock_dir/"image-supervisor.lock").open("a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        worker = execute or partial(codex_imagen, supervisor_fd=lock.fileno())
        statefile = directory/"jobs.json"
        state = json.loads(statefile.read_text()) if statefile.exists() else {}
        attempted = sum(1 for v in state.values() if v.get("attempt"))
        if attempted + len(set(jobs)-state.keys()-supplied.keys()) > limit:
            raise ValueError(f"image authorization insufficient: {len(jobs)} planned; limit {limit}")
        done = {}
        errors = []
        def save():
            atomic_text(statefile,json.dumps(state,ensure_ascii=False,indent=2))
        with ThreadPoolExecutor(max_workers=5) as pool:
            while len(done)<len(jobs):
                work = {}
                for k,r in jobs.items():
                    if k in done or k in errors or not all(ref in done for ref in r["refs"]):
                        continue
                    refs = [done[ref] for ref in r["refs"]]
                    sig = hashlib.sha256(json.dumps([r,[_hash(x) for x in refs],supplied.get(k)],sort_keys=True).encode()).hexdigest()
                    output = directory/(k+".png")
                    if k in supplied:
                        output = (root/supplied[k]).resolve()
                        if not output.is_relative_to(root) or not output.is_file():
                            raise ValueError(f"missing project image: {k}")
                    if k in state:
                        old=state[k]
                        if old.get("sig")==sig and old.get("sha") and output.is_file() and _hash(output)==old["sha"]:
                            done[k]=output
                        else:
                            errors.append(k)
                        continue
                    if k in supplied:
                        state[k]={"sig":sig,"sha":_hash(output),"attempt":False}
                        save()
                        done[k]=output
                        continue
                    if output.exists():
                        errors.append(k)
                        continue
                    state[k]={"sig":sig,"attempt":True,"status":"uncertain"}
                    save()
                    work[pool.submit(worker,r,refs,output)] = (k,output)
                    if len(work)==5:
                        break
                for future in as_completed(work):
                    k,output=work[future]
                    try:
                        future.result()
                        with output.open("rb") as stream:
                            if stream.read(8)!=b"\x89PNG\r\n\x1a\n":
                                raise ValueError("expected PNG")
                        state[k].update(status="available",sha=_hash(output))
                        save()
                        done[k]=output
                    except (OSError,ValueError,subprocess.SubprocessError):
                        errors.append(k)
                if not work and not any(k not in done and k not in errors and all(x in done for x in r["refs"]) for k,r in jobs.items()):
                    break
        if len(done)!=len(jobs):
            raise ValueError("image jobs withheld; inspect jobs.json/log: "+", ".join(sorted(set(jobs)-done.keys())))
        return {k:str(v.relative_to(root)) for k,v in done.items()}
