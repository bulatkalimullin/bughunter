from __future__ import annotations

from pathlib import Path
from typing import Any

from langgraph.graph import END, StateGraph

from bhs.config import Settings
from bhs.nodes.pipeline import (
    ab_tester_node,
    bug_logger_node,
    code_analyzer_node,
    feedback_tick,
    hypervisor_init,
    memory_profiler_node,
    route_feedback,
    route_post_runtime,
    runtime_executor_node,
    test_generator_node,
)
from bhs.sandbox.docker_runner import SandboxRunner
from bhs.state import BHSState
from bhs.storage.artifacts import ArtifactStore


def build_swarm_graph(
    sandbox: SandboxRunner,
    artifacts: ArtifactStore,
    report_dir: Path,
    settings: Settings,
) -> Any:
    g: StateGraph = StateGraph(BHSState)

    g.add_node("hypervisor_init", hypervisor_init)
    g.add_node("code_analyzer", code_analyzer_node)

    def _tg(state: BHSState) -> dict[str, Any]:
        return test_generator_node(state, settings)

    g.add_node("test_generator", _tg)

    def _runtime(state: BHSState) -> dict[str, Any]:
        return runtime_executor_node(state, sandbox, artifacts)

    def _mem(state: BHSState) -> dict[str, Any]:
        return memory_profiler_node(state, artifacts)

    def _ab(state: BHSState) -> dict[str, Any]:
        return ab_tester_node(state, artifacts)

    def _log(state: BHSState) -> dict[str, Any]:
        return bug_logger_node(state, report_dir, settings)

    g.add_node("runtime_executor", _runtime)
    g.add_node("memory_profiler", _mem)
    g.add_node("ab_tester", _ab)
    g.add_node("bug_logger", _log)
    g.add_node("feedback_tick", feedback_tick)

    g.set_entry_point("hypervisor_init")
    g.add_edge("hypervisor_init", "code_analyzer")
    g.add_edge("code_analyzer", "test_generator")
    g.add_edge("test_generator", "runtime_executor")
    g.add_conditional_edges(
        "runtime_executor",
        route_post_runtime,
        {
            "memory": "memory_profiler",
            "ab": "ab_tester",
            "log": "bug_logger",
        },
    )
    g.add_edge("memory_profiler", "bug_logger")
    g.add_edge("ab_tester", "bug_logger")
    g.add_conditional_edges(
        "bug_logger",
        route_feedback,
        {
            "again": "feedback_tick",
            "end": END,
        },
    )
    g.add_edge("feedback_tick", "test_generator")
    return g


def compile_swarm(
    sandbox: SandboxRunner,
    artifacts: ArtifactStore,
    report_dir: Path,
    settings: Settings,
) -> Any:
    return build_swarm_graph(sandbox, artifacts, report_dir, settings).compile()
