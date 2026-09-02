from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from .models import ControlFinding, TraceEvent


def argument_shape(value: Any) -> Any:
    """Return structure and types while intentionally discarding argument values."""
    if isinstance(value, dict):
        return tuple(sorted((key, argument_shape(item)) for key, item in value.items()))
    if isinstance(value, list):
        return ("list", tuple(argument_shape(item) for item in value[:3]))
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    return "string"


def tool_shape(event: TraceEvent) -> tuple[str, Any]:
    return event.name, argument_shape(event.arguments)


def repetition_findings(
    events: Iterable[TraceEvent], threshold: int
) -> list[ControlFinding]:
    findings: list[ControlFinding] = []
    by_task: dict[str, list[TraceEvent]] = defaultdict(list)
    for event in events:
        if event.event_type == "tool":
            by_task[event.task_id].append(event)

    for task_id, task_events in by_task.items():
        previous: tuple[str, Any] | None = None
        run = 0
        first_id = ""
        for event in task_events:
            signature = tool_shape(event)
            if signature == previous:
                run += 1
            else:
                previous = signature
                run = 1
                first_id = event.event_id
            if run == threshold:
                findings.append(
                    ControlFinding(
                        task_id=task_id,
                        control="repeated_tool_shape",
                        severity="warning",
                        evidence=(
                            f"{event.name!r} repeated {threshold} times with the same "
                            f"argument shape ({first_id}..{event.event_id})"
                        ),
                        interpretation=(
                            "Possible loop. This is a structural heuristic, not proof that "
                            "the calls have the same meaning."
                        ),
                    )
                )
    return findings


def find_directed_cycles(edges: Iterable[tuple[str, str]]) -> list[tuple[str, ...]]:
    """Find dependency cycles. A cycle is a warning, not proof of deadlock."""
    graph: dict[str, set[str]] = defaultdict(set)
    for source, target in edges:
        graph[source].add(target)
        graph.setdefault(target, set())

    cycles: set[tuple[str, ...]] = set()
    visiting: list[str] = []
    on_stack: dict[str, int] = {}
    visited: set[str] = set()

    def canonical(nodes: list[str]) -> tuple[str, ...]:
        body = nodes[:-1]
        rotations = [tuple(body[index:] + body[:index]) for index in range(len(body))]
        return min(rotations)

    # Iterative, with an index dict beside the stack. The recursive form had
    # two scale failures: `node in visiting` scanned a list at every visit,
    # O(depth) each, and Python's recursion limit turned a dependency chain
    # a thousand events deep into RecursionError — which the engine's
    # diagnostic guard then reported as "could not run", so cycle detection
    # silently stopped existing exactly when traces got big.
    for root in graph:
        if root in visited:
            continue
        work: list[tuple[str, bool]] = [(root, False)]
        while work:
            node, leaving = work.pop()
            if leaving:
                visiting.pop()
                del on_stack[node]
                visited.add(node)
                continue
            if node in on_stack:
                cycle = visiting[on_stack[node]:] + [node]
                cycles.add(canonical(cycle))
                continue
            if node in visited:
                continue
            on_stack[node] = len(visiting)
            visiting.append(node)
            work.append((node, True))
            for target in graph[node]:
                work.append((target, False))
    return sorted(cycles)
