from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import networkx as nx

from zerion_core.config import settings
from zerion_core.memory.models import JsonStore, TemporalChange


class TemporalGraph:
    """Graphiti-style temporal knowledge graph with change tracking."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or settings.memory_root / "temporal_graph.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.graph = nx.MultiDiGraph()
        self.changes: list[TemporalChange] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        data = json.loads(self.path.read_text(encoding="utf-8"))
        for node in data.get("nodes", []):
            self.graph.add_node(node["id"], **node.get("attrs", {}))
        for edge in data.get("edges", []):
            self.graph.add_edge(
                edge["source"],
                edge["target"],
                key=edge.get("key", 0),
                **edge.get("attrs", {}),
            )
        self.changes = [TemporalChange(**c) for c in data.get("changes", [])]

    def save(self) -> None:
        nodes = [{"id": n, "attrs": dict(self.graph.nodes[n])} for n in self.graph.nodes]
        edges = []
        for u, v, key, attrs in self.graph.edges(keys=True, data=True):
            edges.append({"source": u, "target": v, "key": key, "attrs": dict(attrs)})
        payload = {
            "nodes": nodes,
            "edges": edges,
            "changes": [c.model_dump() for c in self.changes[-500:]],
        }
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def upsert_node(self, node_id: str, attrs: dict[str, Any], reason: str = "") -> None:
        old = dict(self.graph.nodes[node_id]) if node_id in self.graph else {}
        self.graph.add_node(node_id, **attrs, updated_at=datetime.now(timezone.utc).isoformat())
        for key, val in attrs.items():
            old_val = old.get(key)
            if str(old_val) != str(val):
                self.changes.append(
                    TemporalChange(
                        entity=node_id,
                        field=key,
                        old_value=str(old_val) if old_val is not None else None,
                        new_value=str(val),
                        reason=reason,
                    )
                )
        self.save()

    def add_relation(self, source: str, target: str, rel_type: str, **attrs: Any) -> None:
        self.graph.add_edge(source, target, rel_type=rel_type, **attrs)
        self.save()

    def query_neighbors(self, node_id: str, depth: int = 2) -> list[str]:
        if node_id not in self.graph:
            return []
        visited: set[str] = set()
        frontier = {node_id}
        for _ in range(depth):
            nxt: set[str] = set()
            for n in frontier:
                for _, neighbor in self.graph.edges(n):
                    if neighbor not in visited:
                        nxt.add(neighbor)
            visited.update(frontier)
            frontier = nxt - visited
        return list(visited | frontier - {node_id})

    def search_keyword(self, query: str) -> list[dict[str, Any]]:
        q = query.lower()
        results = []
        for node_id, attrs in self.graph.nodes(data=True):
            blob = f"{node_id} {json.dumps(attrs)}".lower()
            if q in blob:
                results.append({"id": node_id, "attrs": dict(attrs), "score": 1.0})
        return results[:20]


class Neo4jGraph:
    """Optional Neo4j backend when configured."""

    def __init__(self) -> None:
        self._driver = None
        if settings.use_neo4j:
            try:
                from neo4j import GraphDatabase

                self._driver = GraphDatabase.driver(
                    settings.neo4j_uri,
                    auth=(settings.neo4j_user, settings.neo4j_password),
                )
            except Exception:
                self._driver = None

    @property
    def available(self) -> bool:
        return self._driver is not None

    def upsert_fact(self, entity: str, key: str, value: str) -> None:
        if not self._driver:
            return
        with self._driver.session() as session:
            session.run(
                """
                MERGE (e:Entity {name: $entity})
                SET e[$key] = $value, e.updated_at = datetime()
                """,
                entity=entity,
                key=key,
                value=value,
            )

    def close(self) -> None:
        if self._driver:
            self._driver.close()
