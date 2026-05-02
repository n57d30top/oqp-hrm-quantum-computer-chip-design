"""Topology construction and graph checks for OQP-HRM meshes."""

from __future__ import annotations


def mzi_pairs(waveguides: int, interferometers: int, stride: int = 3) -> list[tuple[int, int]]:
    if waveguides <= 1:
        raise ValueError("waveguides must be greater than 1")
    if interferometers < 0:
        raise ValueError("interferometers must be non-negative")
    if stride <= 0:
        raise ValueError("stride must be positive")

    pairs: list[tuple[int, int]] = []
    offset = 0
    for _ in range(interferometers):
        m1 = offset % waveguides
        m2 = (offset + 1) % waveguides
        pairs.append((m1, m2))
        offset += stride
    return pairs


def connected_component_count(node_count: int, edges: list[tuple[int, int]]) -> int:
    if node_count <= 0:
        raise ValueError("node_count must be positive")

    parent = list(range(node_count))

    def find(node: int) -> int:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left: int, right: int) -> None:
        root_left = find(left)
        root_right = find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    for left, right in edges:
        union(left, right)

    return len({find(node) for node in range(node_count)})
