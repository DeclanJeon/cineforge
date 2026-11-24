"""Production providers the user can choose once per project (data/providers.yaml).

The list is data: adding a provider is one YAML entry. Availability is read-only,
matched against MCP servers other agents already registered (mcp_discovery).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

LANES = ("video", "image", "voice", "music", "sfx", "avatar")
LANE_LABEL = {"video": "영상 생성", "image": "정지 이미지", "voice": "내레이션·대사", "music": "음악", "sfx": "효과음", "avatar": "아바타·립싱크"}
AUTH = ("oauth", "api_key", "login", "none")
TRANSPORT = ("remote", "local", "cli", "builtin", "none")
DATA = Path(__file__).parent / "data" / "providers.yaml"


def _norm(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def _url_key(url: str | None) -> str | None:
    if not url:
        return None
    parts = urlsplit(url)
    return (parts.netloc.lower() + parts.path.rstrip("/")).lower()


@lru_cache(maxsize=1)
def _doc() -> dict[str, Any]:
    doc = yaml.safe_load(DATA.read_text(encoding="utf-8"))
    seen: set[str] = set()
    for row in doc["providers"]:
        pid = row["id"]
        if pid in seen:
            raise ValueError(f"duplicate_provider: {pid}")
        seen.add(pid)
        if row["auth"] not in AUTH or row["transport"] not in TRANSPORT or not set(row["lanes"]) <= set(LANES) or not row["lanes"]:
            raise ValueError(f"invalid_provider: {pid}")
        if row["transport"] == "remote":
            url = row.get("url") or ""
            if not url.startswith("https://") or url.rstrip("/").endswith("/sse"):
                raise ValueError(f"invalid_provider_url: {pid}")
        if row["auth"] == "api_key" and not row.get("env_var"):
            raise ValueError(f"missing_env_var: {pid}")
    for lane, pid in doc.get("defaults", {}).items():
        if lane not in LANES or pid not in seen:
            raise ValueError(f"invalid_default: {lane}")
    return doc


def load() -> list[dict[str, Any]]:
    return [dict(row) for row in _doc()["providers"]]


def get(pid: str) -> dict[str, Any]:
    for row in _doc()["providers"]:
        if row["id"] == pid:
            return dict(row)
    raise ValueError(f"unknown_provider: {pid}")


def by_lane(lane: str) -> list[dict[str, Any]]:
    if lane not in LANES:
        raise ValueError(f"unknown_lane: {lane}")
    return [dict(row) for row in _doc()["providers"] if lane in row["lanes"]]


def defaults() -> dict[str, str]:
    return dict(_doc().get("defaults", {}))


def parse_flag(text: str) -> dict[str, str]:
    """`video=ludyte,voice=typecast` → {lane: provider id}, validated."""
    out: dict[str, str] = {}
    for part in filter(None, (p.strip() for p in text.split(","))):
        lane, _, pid = (s.strip() for s in part.partition("="))
        if lane not in LANES:
            raise ValueError(f"unknown_lane: {lane}")
        row = get(pid)
        if lane not in row["lanes"]:
            raise ValueError(f"provider_not_in_lane: {pid} does not serve {lane}")
        out[lane] = pid
    return out


def availability(rows: list[dict[str, Any]] | None = None) -> dict[str, bool]:
    """Which providers are already reachable: an installed MCP entry with the same name or URL."""
    if rows is None:
        from .mcp_discovery import discover

        rows = discover()
    names = {_norm(str(r.get("name") or "")) for r in rows}
    urls = {_url_key(r.get("url")) for r in rows if r.get("url")}
    out: dict[str, bool] = {}
    for p in _doc()["providers"]:
        if p["transport"] in ("builtin", "none"):
            out[p["id"]] = True
        else:
            out[p["id"]] = _norm(p["id"]) in names or _norm(p["name"]) in names or _url_key(p.get("url")) in urls
    return out


def question(available: dict[str, bool] | None = None) -> dict[str, Any]:
    """User-only choice payload: every lane with its options and current default."""
    available = availability() if available is None else available
    lanes: dict[str, Any] = {}
    for lane in LANES:
        options = [{"id": p["id"], "name": p["name"], "vendor": p["vendor"], "auth": p["auth"], "billing": p["billing"],
                    "transport": p["transport"], "docs": p.get("docs", ""), "available": bool(available.get(p["id"], False)),
                    **({"notes": p["notes"]} if p.get("notes") else {})} for p in by_lane(lane)]
        options.sort(key=lambda o: (not o["available"], o["transport"] in ("builtin", "none"), o["name"].lower()))
        lanes[lane] = {"label": LANE_LABEL[lane], "default": defaults().get(lane), "options": options}
    return {"lanes": lanes}
