"""공급자 라우팅: 판단은 Jev 1.14 우선 → (키 없으면) 호스트 에이전트/휴리스틱, 생성은 일반 LLM → 호스트/목.

모드
- auto(기본): 판단 [jev-openrouter, jev-typesafe, (에이전트 모드면) host-agent, heuristic]
              생성 [openrouter-gen(모델 지정 시), (에이전트 모드면) host-agent, mock]
- host:       판단 [jev-openrouter, jev-typesafe, host-agent] / 생성 [host-agent]
- openrouter: 판단 [jev-openrouter, jev-typesafe, heuristic] / 생성 [openrouter-gen]
- mock:       판단 [heuristic] / 생성 [mock] (오프라인·테스트)
에이전트 모드: 환경변수 CINEFORGE_AGENT_MODE=1 또는 --provider host.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cineforge.providers.base import (AgentInputRequired, Answer, DecisionProvider, GenerationProvider,
                                      ProviderError, Question)
from cineforge.providers.heuristic import HeuristicDecisionProvider
from cineforge.providers.host_agent import HostAgentDecisionProvider, HostAgentGenerationProvider
from cineforge.providers.mock import MockGenerationProvider
from cineforge.providers.remote import (JevOpenRouterDecisionProvider, JevTypeSafeDecisionProvider,
                                        OpenRouterGenerationProvider)

MODES = ("auto", "host", "openrouter", "mock")
# Set by coding agents in the shells they run; presence means an agent can answer request files.
AGENT_ENV = ("PI_CODING_AGENT", "CLAUDECODE", "CODEX_THREAD_ID", "CODEX_SANDBOX")


def in_agent_context(env: dict[str, str]) -> bool:
    """True when CineForge runs inside a coding agent. CINEFORGE_AGENT_MODE=1/0 forces it on/off."""
    forced = env.get("CINEFORGE_AGENT_MODE")
    if forced in ("0", "1"):
        return forced == "1"
    return any(env.get(name) for name in AGENT_ENV)


@dataclass
class ProviderRouter:
    decision_chain: list[DecisionProvider]
    generation_chain: list[GenerationProvider]
    mode: str = "auto"
    log: list[dict[str, Any]] = field(default_factory=list)
    agent: bool = False  # a host agent answers request files (and must relay user-only choices)

    def decide(self, state: Any, questions: list[Question], task: str = "decision") -> dict[str, Answer]:
        errors: list[str] = []
        for provider in self.decision_chain:
            if not provider.available():
                continue
            try:
                if isinstance(provider, HostAgentDecisionProvider):
                    answers = provider.ask(state, questions, task=task)
                else:
                    answers = provider.ask(state, questions)
            except AgentInputRequired:
                self.log.append({"task": task, "kind": "decision", "provider": provider.name, "status": "waiting_agent"})
                raise
            except ProviderError as exc:
                errors.append(f"{provider.name}: {exc}")
                self.log.append({"task": task, "kind": "decision", "provider": provider.name, "status": "fallback", "error": str(exc)})
                continue
            self.log.append({"task": task, "kind": "decision", "provider": provider.name, "status": "ok"})
            return answers
        raise ProviderError("사용 가능한 판단 공급자가 없습니다: " + "; ".join(errors))

    def generate(self, task: str, payload: dict[str, Any], schema: dict[str, Any] | None = None) -> tuple[dict[str, Any], str]:
        errors: list[str] = []
        for provider in self.generation_chain:
            if not provider.available():
                continue
            try:
                result = provider.generate(task, payload, schema)
            except AgentInputRequired:
                self.log.append({"task": task, "kind": "generation", "provider": provider.name, "status": "waiting_agent"})
                raise
            except ProviderError as exc:
                errors.append(f"{provider.name}: {exc}")
                self.log.append({"task": task, "kind": "generation", "provider": provider.name, "status": "fallback", "error": str(exc)})
                continue
            self.log.append({"task": task, "kind": "generation", "provider": provider.name, "status": "ok"})
            return result, provider.name
        raise ProviderError("사용 가능한 생성 공급자가 없습니다: " + "; ".join(errors))

    def describe(self) -> dict[str, Any]:
        return {"mode": self.mode,
                "decision": [{"name": p.name, "available": p.available()} for p in self.decision_chain],
                "generation": [{"name": p.name, "available": p.available()} for p in self.generation_chain]}


def build_router(mode: str = "auto", io_dir: Path | None = None, env: dict[str, str] | None = None,
                 transport: Any = None) -> ProviderRouter:
    if mode not in MODES:
        raise ValueError(f"알 수 없는 provider 모드: {mode} (가능: {', '.join(MODES)})")
    env = env if env is not None else dict(os.environ)
    io_dir = Path(io_dir) if io_dir else Path.cwd() / "agent_io"
    jev = [JevOpenRouterDecisionProvider(env=env, transport=transport),
           JevTypeSafeDecisionProvider(env=env, transport=transport)]
    agent_mode = mode == "host" or in_agent_context(env)
    gen_remote = OpenRouterGenerationProvider(env=env, transport=transport)
    if mode == "mock":
        return ProviderRouter([HeuristicDecisionProvider()], [MockGenerationProvider()], mode)
    if mode == "host":
        return ProviderRouter(jev + [HostAgentDecisionProvider(io_dir)], [HostAgentGenerationProvider(io_dir)], mode, agent=True)
    if mode == "openrouter":
        return ProviderRouter(jev + [HeuristicDecisionProvider()], [gen_remote], mode)
    decision: list[DecisionProvider] = list(jev)
    generation: list[GenerationProvider] = [gen_remote]
    if agent_mode:
        decision.append(HostAgentDecisionProvider(io_dir))
        generation.append(HostAgentGenerationProvider(io_dir))
    decision.append(HeuristicDecisionProvider())
    generation.append(MockGenerationProvider())
    return ProviderRouter(decision, generation, mode, agent=agent_mode)
