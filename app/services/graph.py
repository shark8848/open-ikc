from __future__ import annotations

from typing import Any

from app.core.error_codes import CommonErrorCodes, KnowledgeBaseException
from app.core.responses import (
    graph_edges_response,
    graph_export_response,
    graph_neighbors_response,
    graph_nodes_response,
    graph_stat_response,
)
from app.services.graph_store import (
    GRAPH_STATUS,
    GraphNodeRecord,
    GraphRelationRecord,
    GraphStore,
    build_document_graph,
    graph_id,
)
from app.services.knowledge_base import KnowledgeBaseService


class GraphService:
    """图谱库（专业库形态）库级视图与加工联动。

    - 只读视图：stat / nodes / edges / neighbors / export，均要求 kbMode=graph；
    - 加工联动：build_from_doc 由解析成功链路调用，按库 graphSchema 抽取并做库级增量融合。
    """

    @staticmethod
    def _require_graph_record(kb_id: str):
        record = KnowledgeBaseService.get_or_raise(kb_id)
        if record.kb_mode != "graph":
            raise KnowledgeBaseException(
                CommonErrorCodes.INVALID_PARAMS,
                {
                    "field": "kbMode",
                    "reason": f"图谱接口仅支持 kbMode=graph 的知识库（当前：{record.kb_mode}）",
                },
            )
        return record

    @staticmethod
    def _schema_coverage(kb_record, stat: dict[str, Any]) -> dict[str, Any]:
        """schema 命中覆盖率：活跃记录中类型被 graphSchema 声明的占比（治理指标）。"""
        schema = dict(kb_record.graph_schema or {})
        declared_entity_types = {
            str(item.get("type", "")).strip()
            for item in (schema.get("entityTypes") or [])
            if isinstance(item, dict) and str(item.get("type", "")).strip()
        }
        declared_relation_types = {
            str(item.get("type", "")).strip()
            for item in (schema.get("relationTypes") or [])
            if isinstance(item, dict) and str(item.get("type", "")).strip()
        }

        def ratio(declared: set[str], types: list[dict[str, Any]]) -> float:
            total = sum(int(item.get("count") or 0) for item in types)
            if total <= 0:
                return 1.0
            hit = sum(int(item.get("count") or 0) for item in types if item.get("type") in declared)
            return round(hit / total, 4)

        entity_coverage = ratio(declared_entity_types, stat["entityTypes"])
        relation_coverage = ratio(declared_relation_types, stat["relationTypes"])
        node_count = int(stat["nodeCount"])
        edge_count = int(stat["edgeCount"])
        total_records = node_count + edge_count
        overall = 1.0
        if total_records > 0:
            overall = round(
                (node_count * entity_coverage + edge_count * relation_coverage) / total_records, 4
            )
        return {
            "entity": entity_coverage,
            "relation": relation_coverage,
            "overall": overall,
        }

    @staticmethod
    def stat(kb_id: str, *, owner_id: str = "", tenant_id: str = "") -> dict[str, Any]:
        record = GraphService._require_graph_record(kb_id)
        stat = GraphStore.stat(kb_id)
        coverage = GraphService._schema_coverage(record, stat)
        return graph_stat_response(
            kb_id=record.kb_id,
            graph_id=graph_id(record.kb_id),
            stat=stat,
            schema_coverage=coverage,
        )

    @staticmethod
    def nodes(
        kb_id: str,
        *,
        entity_type: str = "",
        page: int = 1,
        page_size: int = 20,
        owner_id: str = "",
        tenant_id: str = "",
    ) -> dict[str, Any]:
        record = GraphService._require_graph_record(kb_id)
        records = GraphStore.list_nodes(kb_id, entity_type.strip() or None)
        total = len(records)
        start = (page - 1) * page_size
        return graph_nodes_response(
            kb_id=record.kb_id,
            total=total,
            page=page,
            page_size=page_size,
            records=records[start : start + page_size],
        )

    @staticmethod
    def edges(
        kb_id: str,
        *,
        relation_type: str = "",
        page: int = 1,
        page_size: int = 20,
        owner_id: str = "",
        tenant_id: str = "",
    ) -> dict[str, Any]:
        record = GraphService._require_graph_record(kb_id)
        records = GraphStore.list_edges(kb_id, relation_type.strip() or None)
        total = len(records)
        start = (page - 1) * page_size
        return graph_edges_response(
            kb_id=record.kb_id,
            total=total,
            page=page,
            page_size=page_size,
            records=records[start : start + page_size],
        )

    @staticmethod
    def neighbors(
        kb_id: str,
        *,
        entity_id: str,
        depth: int = 1,
        owner_id: str = "",
        tenant_id: str = "",
    ) -> dict[str, Any]:
        record = GraphService._require_graph_record(kb_id)
        if depth not in (1, 2):
            raise KnowledgeBaseException(
                CommonErrorCodes.INVALID_PARAMS,
                {"field": "depth", "reason": "邻域深度仅支持 1 或 2"},
            )
        center, nodes, edges = GraphStore.neighbors(kb_id, entity_id, depth)
        if center is None:
            raise KnowledgeBaseException(
                CommonErrorCodes.NOT_FOUND,
                {"field": "entityId", "reason": f"图谱实体不存在：{entity_id}"},
            )
        return graph_neighbors_response(
            kb_id=record.kb_id,
            entity_id=entity_id,
            depth=depth,
            center=center,
            nodes=nodes,
            edges=edges,
        )

    @staticmethod
    def export(kb_id: str, *, owner_id: str = "", tenant_id: str = "") -> dict[str, Any]:
        record = GraphService._require_graph_record(kb_id)
        lines = GraphStore.export(kb_id)
        return graph_export_response(
            kb_id=record.kb_id,
            graph_id=graph_id(record.kb_id),
            content="\n".join(lines),
        )

    @staticmethod
    def build_from_doc(
        kb_id: str,
        doc_id: str,
        title: str,
        graph_schema: dict[str, Any] | None = None,
    ) -> tuple[list[GraphNodeRecord], list[GraphRelationRecord]]:
        """解析成功后按库 graphSchema 建图：抽取 → 对齐（type+normalizedName）→ 库级增量融合 → 增量废弃。

        供 ParseService 联动调用；占位阶段单文档生成一个实体节点，真实抽取引擎接入后产出实体/关系。
        """
        nodes, edges = build_document_graph(
            kb_id=kb_id,
            doc_id=doc_id,
            title=title,
            config={"schema": dict(graph_schema or {})},
        )
        saved_nodes = [GraphStore.merge_node(record) for record in nodes]
        saved_edges = [GraphStore.merge_edge(record) for record in edges]
        GraphStore.deprecate_doc_assets(
            kb_id,
            doc_id,
            {f"{record.entity_type}:{record.normalized_name}" for record in nodes},
        )
        return saved_nodes, saved_edges
