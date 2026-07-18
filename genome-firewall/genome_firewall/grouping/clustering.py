from __future__ import annotations

from collections import defaultdict
from typing import Iterable


class _UnionFind:
    def __init__(self, nodes: Iterable[str]):
        self.parent = {node: node for node in nodes}

    def find(self, node: str) -> str:
        while self.parent[node] != node:
            self.parent[node] = self.parent[self.parent[node]]
            node = self.parent[node]
        return node

    def union(self, left: str, right: str) -> None:
        a, b = self.find(left), self.find(right)
        if a != b:
            self.parent[max(a, b)] = min(a, b)


def connected_components(sample_ids: Iterable[str], edges: Iterable[tuple[str, str]]) -> dict[str, str]:
    ids = list(sample_ids)
    if len(ids) != len(set(ids)):
        raise ValueError("sample_ids must be unique")
    union = _UnionFind(ids)
    for left, right in edges:
        if left not in union.parent or right not in union.parent:
            raise ValueError(f"Edge references unknown sample: {(left, right)}")
        union.union(left, right)
    members: dict[str, list[str]] = defaultdict(list)
    for sample in ids:
        members[union.find(sample)].append(sample)
    root_to_group = {root: f"group_{i:05d}" for i, root in enumerate(sorted(members))}
    return {sample: root_to_group[union.find(sample)] for sample in ids}

