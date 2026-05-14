from __future__ import annotations

from pathlib import Path
from typing import Any

from langgraph.graph import END, StateGraph

from bhs.nodes.pipeline import (
    ab_tester_node,
    bug_logger_node,
    code_analyzer_node,
    hypervisor_init,
    memory_profiler_node,
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
) -> Any:
    g: StateGraph = StateGraph(BHSState)

    g.add_node("hypervisor_init", hypervisor_init)
    g.add_node("code_analyzer", code_analyzer_node)
    g.add_node("test_generator", test_generator_node)

    def _runtime(state: BHSState) -> dict[str, Any]:
        return runtime_executor_node(state, sandbox, artifacts)

    def _mem(state: BHSState) -> dict[str, Any]:
        return memory_profiler_node(state, artifacts)

    def _ab(state: BHSState) -> dict[str, Any]:
        return ab_tester_node(state, artifacts)

    def _log(state: BHSState) -> dict[str, Any]:
        return bug_logger_node(state, report_dir)

    g.add_node("runtime_executor", _runtime)
    g.add_node("memory_profiler", _mem)
    g.add_node("ab_tester", _ab)
    g.add_node("bug_logger", _log)

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
    g.add_edge("bug_logger", END)
    return g


def compile_swarm(sandbox: SandboxRunner, artifacts: ArtifactStore, report_dir: Path) -> Any:
    return build_swarm_graph(sandbox, artifacts, report_dir).compile()
