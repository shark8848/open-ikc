from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GraphTypeCount:
    """图谱类型计数（对应平台 GraphTypeCountResponse）。"""

    type: str
    count: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GraphTypeCount":
        return cls(
            type=str(data.get("type", "")),
            count=int(data.get("count") or 0),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "count": self.count,
        }


@dataclass
class GraphStat:
    """图谱库摘要（对应平台 GraphStatDataResponse）。"""

    kbId: str
    kbMode: str = "graph"
    graphId: str = ""
    nodeCount: int = 0
    edgeCount: int = 0
    entityTypes: list[GraphTypeCount] = field(default_factory=list)
    relationTypes: list[GraphTypeCount] = field(default_factory=list)
    schemaCoverage: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GraphStat":
        return cls(
            kbId=str(data.get("kbId", "")),
            kbMode=str(data.get("kbMode", "graph")),
            graphId=str(data.get("graphId", "")),
            nodeCount=int(data.get("nodeCount") or 0),
            edgeCount=int(data.get("edgeCount") or 0),
            entityTypes=[
                GraphTypeCount.from_dict(item)
                for item in (data.get("entityTypes") or [])
                if isinstance(item, dict)
            ],
            relationTypes=[
                GraphTypeCount.from_dict(item)
                for item in (data.get("relationTypes") or [])
                if isinstance(item, dict)
            ],
            schemaCoverage=dict(data.get("schemaCoverage") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kbId": self.kbId,
            "kbMode": self.kbMode,
            "graphId": self.graphId,
            "nodeCount": self.nodeCount,
            "edgeCount": self.edgeCount,
            "entityTypes": [item.to_dict() for item in self.entityTypes],
            "relationTypes": [item.to_dict() for item in self.relationTypes],
            "schemaCoverage": dict(self.schemaCoverage),
        }


@dataclass
class GraphNode:
    """图谱实体节点（对应平台 GraphNodeDetailResponse）。"""

    entityId: str
    type: str
    name: str
    properties: dict[str, Any] = field(default_factory=dict)
    aliases: list[str] = field(default_factory=list)
    evidence: list[dict[str, str]] = field(default_factory=list)
    confidence: float = 0.0
    status: str = ""
    createdAt: str = ""
    updatedAt: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GraphNode":
        return cls(
            entityId=str(data.get("entityId", "")),
            type=str(data.get("type", "")),
            name=str(data.get("name", "")),
            properties=dict(data.get("properties") or {}),
            aliases=[str(alias) for alias in (data.get("aliases") or [])],
            evidence=[dict(item) for item in (data.get("evidence") or []) if isinstance(item, dict)],
            confidence=float(data.get("confidence") or 0.0),
            status=str(data.get("status", "")),
            createdAt=str(data.get("createdAt", "")),
            updatedAt=str(data.get("updatedAt", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "entityId": self.entityId,
            "type": self.type,
            "name": self.name,
            "properties": dict(self.properties),
            "aliases": list(self.aliases),
            "evidence": [dict(item) for item in self.evidence],
            "confidence": self.confidence,
            "status": self.status,
            "createdAt": self.createdAt,
            "updatedAt": self.updatedAt,
        }


@dataclass
class GraphNodes:
    """图谱节点分页结果（对应平台 GraphNodesDataResponse）。"""

    kbId: str
    kbMode: str = "graph"
    total: int = 0
    page: int = 1
    pageSize: int = 20
    items: list[GraphNode] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GraphNodes":
        return cls(
            kbId=str(data.get("kbId", "")),
            kbMode=str(data.get("kbMode", "graph")),
            total=int(data.get("total") or 0),
            page=int(data.get("page") or 1),
            pageSize=int(data.get("pageSize") or 20),
            items=[
                GraphNode.from_dict(item)
                for item in (data.get("items") or [])
                if isinstance(item, dict)
            ],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kbId": self.kbId,
            "kbMode": self.kbMode,
            "total": self.total,
            "page": self.page,
            "pageSize": self.pageSize,
            "items": [node.to_dict() for node in self.items],
        }


@dataclass
class GraphEdge:
    """图谱关系边（对应平台 GraphEdgeDetailResponse）。"""

    relationId: str
    type: str
    sourceEntityId: str
    targetEntityId: str
    properties: dict[str, Any] = field(default_factory=dict)
    evidence: list[dict[str, str]] = field(default_factory=list)
    confidence: float = 0.0
    status: str = ""
    createdAt: str = ""
    updatedAt: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GraphEdge":
        return cls(
            relationId=str(data.get("relationId", "")),
            type=str(data.get("type", "")),
            sourceEntityId=str(data.get("sourceEntityId", "")),
            targetEntityId=str(data.get("targetEntityId", "")),
            properties=dict(data.get("properties") or {}),
            evidence=[dict(item) for item in (data.get("evidence") or []) if isinstance(item, dict)],
            confidence=float(data.get("confidence") or 0.0),
            status=str(data.get("status", "")),
            createdAt=str(data.get("createdAt", "")),
            updatedAt=str(data.get("updatedAt", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "relationId": self.relationId,
            "type": self.type,
            "sourceEntityId": self.sourceEntityId,
            "targetEntityId": self.targetEntityId,
            "properties": dict(self.properties),
            "evidence": [dict(item) for item in self.evidence],
            "confidence": self.confidence,
            "status": self.status,
            "createdAt": self.createdAt,
            "updatedAt": self.updatedAt,
        }


@dataclass
class GraphEdges:
    """图谱边分页结果（对应平台 GraphEdgesDataResponse）。"""

    kbId: str
    kbMode: str = "graph"
    total: int = 0
    page: int = 1
    pageSize: int = 20
    items: list[GraphEdge] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GraphEdges":
        return cls(
            kbId=str(data.get("kbId", "")),
            kbMode=str(data.get("kbMode", "graph")),
            total=int(data.get("total") or 0),
            page=int(data.get("page") or 1),
            pageSize=int(data.get("pageSize") or 20),
            items=[
                GraphEdge.from_dict(item)
                for item in (data.get("items") or [])
                if isinstance(item, dict)
            ],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kbId": self.kbId,
            "kbMode": self.kbMode,
            "total": self.total,
            "page": self.page,
            "pageSize": self.pageSize,
            "items": [edge.to_dict() for edge in self.items],
        }


@dataclass
class GraphNeighbors:
    """实体邻域查询结果（对应平台 GraphNeighborsDataResponse）。"""

    kbId: str
    kbMode: str = "graph"
    entityId: str = ""
    depth: int = 1
    center: GraphNode | None = None
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GraphNeighbors":
        center_data = data.get("center")
        return cls(
            kbId=str(data.get("kbId", "")),
            kbMode=str(data.get("kbMode", "graph")),
            entityId=str(data.get("entityId", "")),
            depth=int(data.get("depth") or 1),
            center=GraphNode.from_dict(center_data) if isinstance(center_data, dict) else None,
            nodes=[
                GraphNode.from_dict(item)
                for item in (data.get("nodes") or [])
                if isinstance(item, dict)
            ],
            edges=[
                GraphEdge.from_dict(item)
                for item in (data.get("edges") or [])
                if isinstance(item, dict)
            ],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kbId": self.kbId,
            "kbMode": self.kbMode,
            "entityId": self.entityId,
            "depth": self.depth,
            "center": self.center.to_dict() if self.center is not None else None,
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
        }


@dataclass
class GraphExport:
    """图谱全量导出结果（对应平台 GraphExportDataResponse）。"""

    kbId: str
    kbMode: str = "graph"
    graphId: str = ""
    format: str = "jsonl"
    total: int = 0
    content: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GraphExport":
        return cls(
            kbId=str(data.get("kbId", "")),
            kbMode=str(data.get("kbMode", "graph")),
            graphId=str(data.get("graphId", "")),
            format=str(data.get("format", "jsonl")),
            total=int(data.get("total") or 0),
            content=str(data.get("content", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kbId": self.kbId,
            "kbMode": self.kbMode,
            "graphId": self.graphId,
            "format": self.format,
            "total": self.total,
            "content": self.content,
        }
