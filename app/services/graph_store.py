from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any


GRAPH_STATUS = {"ACTIVE": "active", "DEPRECATED": "deprecated"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def normalize_name(name: str) -> str:
    """实体名规范化：去除空白与标点、统一小写，用于稳定键派生与同名对齐。"""
    normalized = "".join(ch for ch in (name or "").strip().lower() if ch.isalnum())
    return normalized or "untitled"


def graph_id(kb_id: str) -> str:
    """库级图谱 ID：graph_ + sha1(kbId) 前 12 位，随库生命周期稳定。"""
    digest = hashlib.sha1(kb_id.encode("utf-8")).hexdigest()
    return f"graph_{digest[:12]}"


def entity_id(graph_id_value: str, entity_type: str, normalized_name: str) -> str:
    """稳定实体 ID：ent_ + sha1(graphId + type + normalizedName) 前 12 位，跨文档/跨构建稳定。"""
    digest = hashlib.sha1(f"{graph_id_value}:{entity_type}:{normalized_name}".encode("utf-8")).hexdigest()
    return f"ent_{digest[:12]}"


def relation_id(graph_id_value: str, relation_type: str, source_entity_id: str, target_entity_id: str) -> str:
    """稳定关系 ID：rel_ + sha1(graphId + type + source + target) 前 12 位。"""
    digest = hashlib.sha1(
        f"{graph_id_value}:{relation_type}:{source_entity_id}:{target_entity_id}".encode("utf-8")
    ).hexdigest()
    return f"rel_{digest[:12]}"


@dataclass(frozen=True, slots=True)
class GraphNodeRecord:
    entity_id: str
    graph_id: str
    kb_id: str
    doc_id: str
    entity_type: str
    name: str
    normalized_name: str
    properties: dict[str, Any]
    aliases: list[str]
    evidence: list[dict[str, str]]
    confidence: float
    status: str
    created_at: str
    updated_at: str

    def evidence_doc_ids(self) -> set[str]:
        """证据来源文档 ID 集合（用于增量废弃判定）。"""
        return {str(item.get("docId") or "") for item in self.evidence}


@dataclass(frozen=True, slots=True)
class GraphRelationRecord:
    relation_id: str
    graph_id: str
    kb_id: str
    doc_id: str
    relation_type: str
    source_entity_id: str
    target_entity_id: str
    properties: dict[str, Any]
    evidence: list[dict[str, str]]
    confidence: float
    status: str
    created_at: str
    updated_at: str


class GraphStore:
    """进程内图谱库存储（占位实现）。

    仅负责原子读写、按稳定 ID 增量合并与邻域/导出派生，业务校验与异常语义由 service 层承担。
    """

    _lock = threading.Lock()
    _nodes: dict[str, GraphNodeRecord] = {}
    _edges: dict[str, GraphRelationRecord] = {}

    @classmethod
    def merge_node(cls, record: GraphNodeRecord) -> GraphNodeRecord:
        """按 entityId 增量合并：追加别名与证据，置信度取较大值，正文/属性以新内容为准。"""
        with cls._lock:
            existing = cls._nodes.get(record.entity_id)
            if existing is None:
                cls._nodes[record.entity_id] = record
                return record
            merged = replace(
                record,
                created_at=existing.created_at,
                aliases=sorted(set(existing.aliases) | set(record.aliases)),
                evidence=existing.evidence + [item for item in record.evidence if item not in existing.evidence],
                confidence=max(existing.confidence, record.confidence),
            )
            cls._nodes[record.entity_id] = merged
            return merged

    @classmethod
    def merge_edge(cls, record: GraphRelationRecord) -> GraphRelationRecord:
        """按 relationId 增量合并：追加证据，冲突（属性/置信度）以 updatedAt 后者优先。"""
        with cls._lock:
            existing = cls._edges.get(record.relation_id)
            if existing is None:
                cls._edges[record.relation_id] = record
                return record
            merged = replace(
                record,
                created_at=existing.created_at,
                evidence=existing.evidence + [item for item in record.evidence if item not in existing.evidence],
                confidence=max(existing.confidence, record.confidence),
            )
            cls._edges[record.relation_id] = merged
            return merged

    @classmethod
    def get_node(cls, entity_id: str) -> GraphNodeRecord | None:
        with cls._lock:
            return cls._nodes.get(entity_id)

    @classmethod
    def get_edge(cls, relation_id: str) -> GraphRelationRecord | None:
        with cls._lock:
            return cls._edges.get(relation_id)

    @classmethod
    def list_nodes(
        cls,
        kb_id: str,
        entity_type: str | None = None,
        *,
        include_deprecated: bool = False,
    ) -> list[GraphNodeRecord]:
        with cls._lock:
            records = [
                record
                for record in cls._nodes.values()
                if record.kb_id == kb_id
                and (include_deprecated or record.status == GRAPH_STATUS["ACTIVE"])
                and (entity_type is None or record.entity_type == entity_type)
            ]
            return sorted(records, key=lambda item: (item.entity_type, item.name))

    @classmethod
    def list_edges(
        cls,
        kb_id: str,
        relation_type: str | None = None,
        *,
        include_deprecated: bool = False,
    ) -> list[GraphRelationRecord]:
        with cls._lock:
            records = [
                record
                for record in cls._edges.values()
                if record.kb_id == kb_id
                and (include_deprecated or record.status == GRAPH_STATUS["ACTIVE"])
                and (relation_type is None or record.relation_type == relation_type)
            ]
            return sorted(records, key=lambda item: (item.relation_type, item.relation_id))

    @classmethod
    def neighbors(
        cls,
        kb_id: str,
        entity_id: str,
        depth: int = 1,
    ) -> tuple[GraphNodeRecord, list[GraphNodeRecord], list[GraphRelationRecord]]:
        """实体邻域（BFS）：返回中心节点、可达节点与覆盖边；depth 仅允许 1/2（service 层校验）。"""
        with cls._lock:
            center = cls._nodes.get(entity_id)
            if center is None or center.kb_id != kb_id:
                return None, [], []
            node_by_id = {
                record.entity_id: record
                for record in cls._nodes.values()
                if record.kb_id == kb_id and record.status == GRAPH_STATUS["ACTIVE"]
            }
            edges = [
                record
                for record in cls._edges.values()
                if record.kb_id == kb_id and record.status == GRAPH_STATUS["ACTIVE"]
            ]
        reachable: dict[str, GraphNodeRecord] = {center.entity_id: center}
        covered: dict[str, GraphRelationRecord] = {}
        frontier = {center.entity_id}
        for _ in range(depth):
            next_frontier: set[str] = set()
            for edge in edges:
                if edge.source_entity_id in frontier:
                    target = node_by_id.get(edge.target_entity_id)
                    if target is not None:
                        covered[edge.relation_id] = edge
                        next_frontier.add(target.entity_id)
                if edge.target_entity_id in frontier:
                    source = node_by_id.get(edge.source_entity_id)
                    if source is not None:
                        covered[edge.relation_id] = edge
                        next_frontier.add(source.entity_id)
            for node_id in next_frontier:
                reachable.setdefault(node_id, node_by_id[node_id])
            frontier = next_frontier
        return center, list(reachable.values()), list(covered.values())

    @classmethod
    def stat(cls, kb_id: str) -> dict[str, Any]:
        """图谱摘要：节点/边计数与类型分布（活跃记录）。"""
        nodes = cls.list_nodes(kb_id)
        edges = cls.list_edges(kb_id)
        entity_types: dict[str, int] = {}
        for record in nodes:
            entity_types[record.entity_type] = entity_types.get(record.entity_type, 0) + 1
        relation_types: dict[str, int] = {}
        for record in edges:
            relation_types[record.relation_type] = relation_types.get(record.relation_type, 0) + 1
        return {
            "nodeCount": len(nodes),
            "edgeCount": len(edges),
            "entityTypes": [{"type": key, "count": value} for key, value in sorted(entity_types.items())],
            "relationTypes": [{"type": key, "count": value} for key, value in sorted(relation_types.items())],
        }

    @classmethod
    def export(cls, kb_id: str) -> list[str]:
        """全量导出 jsonl 行：entity/relation 记录（含 deprecated，保审计）。"""
        lines: list[str] = []
        with cls._lock:
            for record in sorted(cls._nodes.values(), key=lambda item: item.entity_id):
                if record.kb_id != kb_id:
                    continue
                lines.append(json.dumps({
                    "kind": "entity",
                    "entityId": record.entity_id,
                    "type": record.entity_type,
                    "name": record.name,
                    "properties": record.properties,
                    "aliases": record.aliases,
                    "evidence": record.evidence,
                    "confidence": record.confidence,
                    "status": record.status,
                }, ensure_ascii=False))
            for record in sorted(cls._edges.values(), key=lambda item: item.relation_id):
                if record.kb_id != kb_id:
                    continue
                lines.append(json.dumps({
                    "kind": "relation",
                    "relationId": record.relation_id,
                    "type": record.relation_type,
                    "sourceEntityId": record.source_entity_id,
                    "targetEntityId": record.target_entity_id,
                    "properties": record.properties,
                    "evidence": record.evidence,
                    "confidence": record.confidence,
                    "status": record.status,
                }, ensure_ascii=False))
        return lines

    @classmethod
    def deprecate_doc_assets(cls, kb_id: str, doc_id: str, active_entity_keys: set[str]) -> int:
        """增量废弃：仅由该文档贡献、且本次构建未再出现的节点标记 deprecated（不物理删除，保审计）。"""
        deprecated = 0
        with cls._lock:
            for entity_id, record in list(cls._nodes.items()):
                if record.kb_id != kb_id or doc_id not in record.evidence_doc_ids():
                    continue
                key = f"{record.entity_type}:{record.normalized_name}"
                if key in active_entity_keys:
                    continue
                if record.evidence_doc_ids() != {doc_id}:
                    continue
                if record.status == GRAPH_STATUS["ACTIVE"]:
                    cls._nodes[entity_id] = replace(record, status=GRAPH_STATUS["DEPRECATED"], updated_at=_now_iso())
                    deprecated += 1
        return deprecated

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._nodes.clear()
            cls._edges.clear()


def build_document_graph(
    *,
    kb_id: str,
    doc_id: str,
    title: str,
    config: dict[str, Any] | None = None,
) -> tuple[list[GraphNodeRecord], list[GraphRelationRecord]]:
    """按 graphSchema 生成文档图谱（占位实现：单文档生成一个实体节点，待抽取引擎接入后产出真实实体/关系）。

    实体类型取 schema 首个 entityTypes[].type，未定义 schema 时使用通用类型 concept；
    节点名取文档标题，证据挂接 docId。链路（建点→对齐合并→统计/邻域/导出）完整可验证。
    """
    config = dict(config or {})
    schema = dict(config.get("schema") or config.get("graphSchema") or {})
    entity_types = schema.get("entityTypes") or []
    if entity_types and isinstance(entity_types[0], dict) and str(entity_types[0].get("type", "")).strip():
        entity_type = str(entity_types[0]["type"]).strip()
    else:
        entity_type = "concept"
    title = (title or "").strip() or "未命名文档"
    gid = graph_id(kb_id)
    now = _now_iso()
    record = GraphNodeRecord(
        entity_id=entity_id(gid, entity_type, normalize_name(title)),
        graph_id=gid,
        kb_id=kb_id,
        doc_id=doc_id,
        entity_type=entity_type,
        name=title,
        normalized_name=normalize_name(title),
        properties=dict(config.get("properties") or {}),
        aliases=[],
        evidence=[{"docId": doc_id}],
        confidence=float(config.get("confidence") or 0.9),
        status=GRAPH_STATUS["ACTIVE"],
        created_at=now,
        updated_at=now,
    )
    return [record], []
