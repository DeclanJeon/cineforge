# Provider Registry & All-Agent MCP Registration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Users pick production providers (video, image, voice, music, sfx, avatar) once at project start — in the interactive CLI, or relayed by a host agent as a user-only choice — and `cineforge providers setup <id>` registers the chosen MCP server in every installed agent.

**Approved design (2026-11-24):** timing A (ask once at start, with the concept). Scope (a): video, image, voice, music, sfx, avatar. Research: `docs/research/2026-11-24-media-provider-mcp.md`.

**Architecture:** A data file lists providers. `provider_registry.py` loads it and marks availability from existing read-only MCP discovery. `agent_register.py` plans and applies registration per agent through an injectable command runner, so tests never touch real configs. The pipeline asks once per project and stores the answer in `project.json inputs.providers`. The voice choice drives the existing dialogue routing.

**Tech stack:** Python 3.10+, PyYAML (already used), pytest.

## Files
- Create `cineforge/data/providers.yaml`: entries `{id, name, vendor, lanes[], transport: remote|local|builtin|none, url?, command?, auth: oauth|api_key|login|none, env_var?, docs, billing, notes?}`; plus `defaults: {lane: id}`.
- Create `cineforge/provider_registry.py`:
  - `LANES = ("video", "image", "voice", "music", "sfx", "avatar")`
  - `load() -> list[dict]` (validated: unique ids, known lanes/auth/transport, remote needs https url not ending /sse)
  - `by_lane(lane) -> list[dict]`, `get(id) -> dict`
  - `availability(rows=None) -> dict[id, bool]`: matched against discovered MCP entries by normalized name or URL host+path; builtin/none → True.
  - `parse_flag("video=ludyte,voice=typecast") -> dict` (validates lane and that the provider serves it)
  - `question() -> dict`: user_choice payload (lanes → options with label, auth, billing, available, docs).
- Create `cineforge/agent_register.py`:
  - `AGENTS`: pi (`pi mcp add NAME --url URL`), codex (`codex mcp add NAME --url URL [--bearer-token-env-var VAR]`), opencode (`opencode mcp add NAME --global --url URL [--header Authorization=Bearer {env:VAR}]`), gemini (JSON edit of `~/.gemini/settings.json` mcpServers `{httpUrl, headers?}`), claude (`claude mcp add --transport http -s user NAME URL`).
  - `detect(home, which) -> list[str]`: agent counted if its CLI is on PATH or (gemini) its settings file exists.
  - `plan(provider, agents, existing) -> list[Step]`: Step `{agent, action: add|skip|manual, command?|file?, reason}`; skip when same normalized name or same URL already registered for that agent; local/builtin providers → manual instructions.
  - `apply(steps, run, home) -> list[result]`: runs commands via injected `run`; gemini file edit makes `settings.json.cineforge.bak` first; never writes secret values.
  - `login_hints(provider, agents) -> list[str]` (pi `pi mcp login`, codex `codex mcp login`, others: open /mcp).
- Modify `cineforge/cli.py`: `providers list [--lane L] [--json]`, `providers setup ID [--agents a,b] [--dry-run]`, `new --providers lane=id,...` (alias: `--voice-provider` sets voice), interactive provider step after concept selection.
- Modify `cineforge/providers/host_agent.py`: `user_choice(task, payload)` writes a request with `kind: "user_choice"`, `must_ask_user: true`, relay instructions, and requires `{"choices": {lane: id}, "user_said": str}`.
- Modify `cineforge/pipeline.py` `_s01`: if `inputs.providers` missing — host provider → user_choice request (stage waiting_user); otherwise defaults. Store choice; voice choice sets `inputs.voice_provider`/`external_voice`.
- Modify skill `cineforge-production` handoff text in `cineforge/skill_handoff.py` or README section: relay user_choice verbatim.
- Tests: `tests/test_provider_registry.py`, `tests/test_agent_register.py`, `tests/test_provider_choice.py`.

## Tasks
- [ ] T1 Registry data + loader + validation + availability + flag parsing (tests first).
- [ ] T2 Agent registration planner/applier with fake runner + tmp HOME; skip duplicates; gemini backup; dry-run (tests first).
- [ ] T3 CLI `providers list/setup` (tests via main()).
- [ ] T4 Project choice: `--providers`, host user_choice block + resume, mock defaults, voice wiring, interactive step with injected ask (tests first).
- [ ] T5 Full suite, docs (README section), commit.
- [ ] T6 QA: real `providers list`, `setup --dry-run` on this machine, interactive run via pty, host-mode user_choice end-to-end; report gaps.
