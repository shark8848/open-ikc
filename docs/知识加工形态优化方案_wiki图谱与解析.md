# 知识加工与专业库形态优化方案：文本库 / Wiki 库 / 图谱库

> 文档日期：2026-08-18（v2，方向修正）
> 状态：方案评审稿；**P1（kbMode 形态协议）已落地（2026-08-18）**，**P2（Wiki 库）已落地（2026-08-18）**，**P3（图谱库）已落地（2026-08-18）**，P4 待评审后实施
> 产品决策：**Wiki、图谱定义为专业的知识库形态（专业库）**，而非解析产物形态。
> 范围：面向「知识加工」的对外 API 定义优化，重点设计 Wiki 库与图谱库的构建与访问。

## 1. 背景与目标

当前平台的「知识库」只有一种形态：**文本/文档库**（kbType 表达 personal/team/enterprise 的归属与可见范围，内容为文档 + 解析文本 + 检索索引）。实际业务需要另外两种**专业库**：

- **Wiki 库**：把资料集加工成百科式**页面树**（页面互链、结构化字段），适合知识门户、新人培训、FAQ、制度流程库；
- **图谱库**：把资料集加工成**实体—关系网络**（组织架构、产品矩阵、事件因果、权限关联），适合以实体为中心的查询与多跳推理。

产品决策：Wiki 库与图谱库是**知识库层级的专业形态**——建库即声明形态，文档加工进库后自动按库形态构建产物，产物作为**库级资产**跨文档合并、随库查询。

本方案回答：如何在现有四类能力边界内定义「专业库形态」，以及 Wiki 库、图谱库的构建协议、库级产物模型与访问接口。

## 2. 现状与差距

| 项 | 现状 | 差距 |
| --- | --- | --- |
| 知识库形态 | 仅文本/文档库；`kbType` 表达归属维度（personal/team/enterprise） | 无「形态」维度，无法声明 wiki/图谱库 |
| 加工产物 | 解析产物仅 json/markdown/text（普通解析） | 无页面树、无实体/关系产物 |
| 库级资产 | 无（内容挂在 doc/parse-task 下） | wiki 页面树、库级图谱无归属与查询入口 |
| 检索 | 全文检索（in_process 占位 / ur / openai） | 无法按库形态路由（页面检索、实体邻域检索） |

核心差距：**库只有「归属维度」，没有「形态维度」**。Wiki/图谱需要的是库的内容组织方式（页面树 / 实体关系网），与归属（谁可见）正交。

## 3. 核心设计：知识库形态维度 `kbMode`

### 3.1 两个正交维度

| 维度 | 字段 | 取值 | 语义 |
| --- | --- | --- | --- |
| 归属/可见范围 | `kbType`（现有） | `personal` / `team` / `enterprise` | 谁可见、谁可写（不变） |
| **库形态** | `kbMode`（新增） | `text`（默认，兼容现状）/ `wiki` / `graph` | 库的内容组织与加工方式 |

- 任一 `kbType` 都可叠加任一 `kbMode`（如「企业 Wiki 库」= `kbType=enterprise, kbMode=wiki`）；
- 权限模型完全复用现有 `kbType` 约束，形态不引入新的权限维度；
- 缺省 `kbMode=text`，存量库与存量调用零影响。

### 3.2 能力归属（不扩大能力面）

| 能力域 | 承担职责 |
| --- | --- |
| 知识库管理 | 定义与维护库形态：`kbMode` + 形态配置（`wikiConfig` / `graphSchema`），创建/修改/查询 |
| 文档接入 | 不变（ingest 登记来源） |
| 解析（知识加工） | 按库形态加工：`parse` 产物形态缺省跟随 `kbMode`；免库场景显式 `productType` |
| 检索 | 按库形态路由检索（文本检索 / 页面检索 / 实体检索），见 §8 |

Wiki/图谱**不新增第五类业务域**：形态在知识库域定义，加工在解析域执行，产物查询挂库维度（§5/§6），全部落在既有四类内。

## 4. 专业库定义协议

### 4.1 创建 / 修改 / 查询

`POST /api/v1/knowledge-bases/create`、`POST /api/v1/knowledge-bases/update` 请求体新增：

| 字段 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `kbMode` | enum | 否 | `text` | 库形态：`text` / `wiki` / `graph` |
| `wikiConfig` | object | 否 | `{}` | `kbMode=wiki` 时建议传，见 §5.2 |
| `graphSchema` | object | 否 | `{}` | `kbMode=graph` 时建议传，见 §6.2 |

- `knowledge-bases/query` / `GET {kb_id}` 响应 `data` 新增 `kbMode`、`wikiConfig`、`graphSchema`（形态配置随库返回，调用方据此适配消费方式）；
- `update` 允许修改形态配置；**允许 text↔wiki 双向、text↔graph 双向、wiki↔graph 需产品确认**（页面树↔图谱互转成本高，默认拒绝返回 `100409` 形态冲突，见 §11 开放问题）；
- 形态配置的合法性校验沿用 `100001` 参数错误映射。

### 4.2 加工联动

`parse` / `ingest-and-parse` 请求体新增可选 `productType`（`text` / `wiki` / `graph`），规则：

1. **缺省跟随库形态**：不传时 `parse` 按 `kbMode` 产出（text 库→文本，wiki 库→页面，graph 库→图谱）；免库 `parse-direct` 不传时默认 `text`；
2. **显式覆盖**：允许在库形态内覆盖（如 wiki 库内对单文档做 `productType=text` 草稿解析）；跨形态（text 库产图谱）**拒绝**，避免库内容形态混乱，返回 `100001` 并提示先建对应形态库；
3. `parse-direct`（免库）保留 `productType=wiki|graph` 的一次性加工能力（不建库场景，图谱仅 `graphScope=doc`），与专业库并行。

## 5. Wiki 库（重点设计）

### 5.1 库级产物模型

Wiki 库的核心资产是**库级页面树**（跨文档合并）：

- **页面**：`pageId` + `title` + `level` + `parentPageId` + `markdown` 正文 + `fields`（结构化字段）+ `tags` + `links[]`（`[[页面标题]]` 互链）+ `sourceDocs[]`（来源文档/分块证据）+ `status`（active/deprecated）+ `updatedAt`；
- **稳定 ID**：`pageId = wiki_ + sha1(kbId + stableKey)[:12]`，`stableKey` 由标题规范化生成——跨文档、跨构建保持稳定，同名条目自动合并；
- **跨文档合并**：不同文档加工出同标题页面时按 `dedup` 策略合并（§5.2），页面链接可跨文档解析（A 文档提到 B 文档的条目即建立 wiki-link）。

### 5.2 库配置 `wikiConfig`

| 字段 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `granularity` | enum | `auto` | 条目粒度：`auto`（按标题结构智能切页）/ `heading`（h1/h2 起页）/ `section` / `page`（整文档一页） |
| `extractFields` | array<string> | `[]` | 全局抽取的结构化字段名（如 `["负责人","版本","生效日期"]`），可被任务级覆盖 |
| `linkMode` | enum | `auto` | 页面互链：`auto` / `off` |
| `dedup` | enum | `merge` | 同名条目策略：`merge`（合并证据）/ `overwrite` / `skip` |
| `template` | string | `""` | 页面模板/提示词，约束页面结构与字段抽取 |

### 5.3 构建流程（解析域内部编排）

```
文档 → 分块/布局解析（复用普通解析）→ 按 granularity 切页 → 页面生成（标题/正文/fields）
     → 跨文档页面对齐（kbId+stableKey）→ dedup 合并 → wiki-link 解析 → 页面入库 → 可选进检索索引
```

要点：

1. 任务级 `wikiStrategy` 覆盖库级 `wikiConfig` 的同名字段（沿用「显式配置优先于全局默认」约定）；
2. 增量：重复加工按 stableKey 定位旧页，merge 追加证据、overwrite 替换、skip 保留；不再出现的章节标记 `deprecated`（不物理删除，保审计）；
3. 页面进入检索索引后，Wiki 库检索返回页面粒度命中（§8）。

### 5.4 库级访问接口

新增（只读，权限沿用库权限：个人库仅创建者 / 团队 / 企业按授权）：

| 接口 | 方法 | 说明 |
| --- | --- | --- |
| `GET /api/v1/knowledge-bases/{kb_id}/wiki/tree` | GET | 库级页面树（含 pageId/title/level/层级，支持 `page`/`pageSize`） |
| `GET /api/v1/knowledge-bases/{kb_id}/wiki/page` | GET | 单页内容（`pageId` 必填：正文 + fields + links + sourceDocs） |
| `GET /api/v1/knowledge-bases/{kb_id}/wiki/search` | GET | 库内页面检索（`q` + 可选 `tag` 过滤），返回页面级命中 |

- 不存在的 `kbMode=text` 库调用 wiki 接口返回 `100001`（形态不匹配）；wiki 库无页面返回空树（非错误）；
- 单文档加工状态仍走 `parse-result/query`；库级视图由此接口提供。

## 6. 图谱库（重点设计）

### 6.1 库级产物模型

图谱库的核心资产是**库级知识图谱**（多文档增量融合）：

- **节点（entity）**：`entityId` + `type` + `name` + `properties` + `aliases` + `evidence[]`（docId/pageId/chunkId/offset/原文）+ `confidence` + `status`；
- **边（relation）**：`relationId` + `type` + `sourceEntityId` + `targetEntityId` + `properties` + `evidence[]` + `confidence` + `status`；
- **库级图谱**：`graphId = graph_ + sha1(kbId)[:12]`，随库生命周期；图谱库默认 `graphScope=kb`（多文档并入同一图谱），免库一次性加工仅 `graphScope=doc`；
- **稳定 ID**：`entityId = ent_ + sha1(graphId + type + normalizedName)[:12]`（exact 对齐下即唯一键），跨文档、跨构建稳定。

### 6.2 库配置 `graphSchema`

图谱库的质量闸门，建库时建议定义，加工时严格按 schema 抽取：

| 字段 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `entityTypes` | array<object> | `[]` | `{type, description}`，允许的实体类型 |
| `relationTypes` | array<object> | `[]` | `{type, sourceTypes[], targetTypes[], description}`，允许的关系类型及两端实体约束 |

不传 schema 时用默认宽松 schema（通用类型），但会在 `graph/stat` 返回 `schemaCoverage`（命中 schema 的实体/边占比）供治理。

### 6.3 构建策略（任务级 `graphStrategy` 覆盖库配置）

| 字段 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `graphScope` | enum | 跟随库 | 图谱库固定 `kb`；免库仅 `doc` |
| `schema` | object | 库 schema | 任务级 schema 覆盖（须为库 schema 子集） |
| `extraction` | enum | `auto` | 抽取方式：`auto`（规则 + LLM 混合）/ `llm` |
| `model` | object | `{}` | LLM 抽取模型（复用 `parseStrategy.enhancement.modelList` 单条语义） |
| `identityResolution` | enum | `exact` | 实体对齐：`exact`（type+name 归一）/ `fuzzy`（LLM 同义）/ `off` |
| `minConfidence` | number | `0.5` | 关系置信度阈值（0–1），低于阈值丢弃 |
| `maxEntities` | int | `5000` | 单任务新增实体上限，防爆量 |

### 6.4 构建流程（解析域内部编排）

```
文档 → 分块 → 实体抽取（schema 约束 entityTypes）→ 关系抽取（校验 relationTypes 的 source/target）
     → 实体对齐（identityResolution：type+normalizedName 归一 / LLM 同义）→ 置信度过滤（minConfidence）
     → 证据挂接 → 并入库级图谱（旧实体追加证据、旧边冲突按 updatedAt 后者优先）
```

要点：

1. **schema 是质量闸门**：抽取结果类型不在 schema 内直接丢弃，`failedReason` 记录统计，避免图谱噪声；
2. **对齐是增量核心**：`(type, normalizedName)` 唯一键保证重复加工合并而非重复建点；`aliases` 累积别名；
3. **证据可追溯**：节点/边都带 `evidence[]`，图谱结论可回链原文（与检索 citations 语义一致）；
4. **删除语义**：不再出现的实体/边标记 `deprecated`（保留历史与引用安全）；
5. 库级并发：图谱库多文档加工任务串行并入（P3 内部队列），避免并发合并冲突。

### 6.5 库级访问接口

新增（只读，权限同库权限）：

| 接口 | 方法 | 说明 |
| --- | --- | --- |
| `GET /api/v1/knowledge-bases/{kb_id}/graph/stat` | GET | 图谱摘要：nodeCount/edgeCount、类型分布、schemaCoverage |
| `GET /api/v1/knowledge-bases/{kb_id}/graph/nodes` | GET | 分页节点（`entityType` 过滤，`page`/`pageSize`） |
| `GET /api/v1/knowledge-bases/{kb_id}/graph/edges` | GET | 分页关系（`relationType` 过滤） |
| `GET /api/v1/knowledge-bases/{kb_id}/graph/neighbors` | GET | 实体邻域（`entityId` + `depth=1|2`），实体中心消费 |
| `GET /api/v1/knowledge-bases/{kb_id}/graph/export` | GET | 全量导出（jsonl：entity/relation 记录），走下载凭证 |

- 分页强制（nodes/edges），`neighbors` 限 `depth≤2`，`export` 复用 `issue-download-ticket` 链路；
- `kbMode=text` 库调用图谱接口返回 `100001`；空图谱返回空统计（非错误）。

## 7. 普通解析的配套优化

1. **语义收敛**：`resultFormat.type` 明确为「文本产物序列化格式」（json/markdown/text），与库形态解耦；`productType=text` 显式等价；
2. **download 落地**：`parse-result/download` 从元数据占位升级为真实产物流（text/markdown/json；wiki 页面导出 jsonl；图谱 nodes/edges jsonl），与 `upload` 端点二进制流形态对齐；
3. **摘要字段**：`parse-result/query` 返回 `productType` 与形态摘要（text: `format`；wiki: `pageCount`；graph: `nodeCount/edgeCount`），供调用方分流。

## 8. 检索衔接（按库形态路由）

| 库形态 | 检索语义 | 建议载体 |
| --- | --- | --- |
| text 库 | 全文检索（现状不变） | `universal-search` |
| wiki 库 | 页面粒度检索 + 可选沿 `wiki-link` 扩展候选 | `universal-search` 扩展 `searchMode=page`；或 `wiki/search` |
| graph 库 | 实体识别 → 邻域扩展 → 证据段落召回（多跳） | `deep-search` 实体多跳；`graph/neighbors` 供应用层自行编排 |

- 平台 `in_process` 占位后端下，wiki/graph 检索增强先以结构化 501001/占位返回（沿用现有 deep-search 策略），待 `ur`/`openai` 后端接入启用；
- 权限不降级：检索过滤沿用 kb 权限（含形态库）。

## 9. 数据模型与增量策略（内部落地参考）

| 存储 | 关键字段 | 稳定 ID 策略 |
| --- | --- | --- |
| `KnowledgeBaseRecord` | + `kb_mode`、`wiki_config`、`graph_schema` | 现有 kbId |
| `ParseTaskRecord` | + `product_type` | 现有 taskId |
| `WikiPageRecord` | pageId, kbId, title, level, parentPageId, stableKey, fields, markdown, links, sourceDocs, status, updatedAt | `wiki_` + sha1(kbId + stableKey)[:12] |
| `GraphRecord` | graphId, kbId, nodeCount, edgeCount, schemaCoverage, updatedAt | `graph_` + sha1(kbId)[:12] |
| `GraphEntityRecord` | entityId, graphId, type, name, aliases, properties, evidence, confidence, status | `ent_` + sha1(graphId + type + normalizedName)[:12] |
| `GraphRelationRecord` | relationId, graphId, type, sourceEntityId, targetEntityId, properties, evidence, confidence, status | `rel_` + 随机 |

增量约定：重复加工按稳定 ID 定位旧记录（merge/overwrite/skip）；不再出现的资产标记 `deprecated`；库级并发任务串行合并。

## 10. 落地分期

| 阶段 | 内容 | 改动面 |
| --- | --- | --- |
| P1 | `kbMode` 协议：create/update/query/detail 支持形态与配置 + 校验 + catalog + 文档 | `app/schemas/knowledge_base.py`、`app/services/knowledge_base.py`、`app/core/catalog.py`、手册 |
| P2 | Wiki 库：`wikiConfig` + 库级页面存储 + `wiki/tree|page|search` + `parse` 联动 | **已落地**：`app/services/wiki_store.py`（页面记录/合并/树/检索/增量废弃）、`app/services/wiki.py`、`app/schemas/wiki.py`、路由与 catalog、`sync` 解析自动建页、`tests/test_wiki_library.py` 10 例 |
| P3 | 图谱库：`graphSchema` + 抽取编排（auto 规则 + LLM 可配）+ `graph/stat|nodes|edges|neighbors|export` + 串行合并 | **已落地**：`app/services/graph_store.py`（节点/边存储、稳定 ID 增量合并、邻域/统计/导出）、`app/services/graph.py`、`app/schemas/graph.py`、路由与 catalog、`sync` 解析自动建图、`tests/test_graph_library.py` 9 例、SDK/MCP/CLI graph 五工具/命令 |
| P4 | 检索消费侧：wiki 页面检索、图谱多跳 | 依赖真实检索后端 |

建议：P1 先行（形态协议铺路，向后兼容）；P2（Wiki 库）与 P3（图谱库）按业务优先级二选一先行；图谱 LLM 成本需产品确认。

## 11. 风险与开放问题

| 风险/问题 | 说明 | 建议 |
| --- | --- | --- |
| 形态互转 | text↔wiki 可双向（页面可回退为文本）；wiki↔graph 互转成本高 | 默认拒绝 `100409`；需要时产品评审后单独支持 |
| 能力边界 | 图谱库是否会视为第五类能力 | 已收敛：形态在知识库域、加工在解析域；若产品独立定义图谱域，先对齐 AGENTS.md |
| LLM 成本 | wiki 字段抽取、图谱抽取与 fuzzy 对齐吃模型预算 | `extraction=auto` 规则优先、`maxEntities` 上限、`identityResolution` 默认 exact |
| 图谱噪声 | 无 schema 约束时抽取失控 | 建议建库必传 `graphSchema`；返回 `schemaCoverage` 供治理 |
| 产物规模 | 大库图谱上万节点 | nodes/edges 强制分页、neighbors 限深、export 走下载凭证 |
| 并发一致性 | 图谱库多文档并发加工合并冲突 | 任务串行并入（P3 内部队列），冲突按 updatedAt 后者优先 |
| 检索后端 | wiki/graph 检索增强依赖真实后端 | P1–P3 只做库形态与产物；P4 待后端就绪 |

## 12. 与现有实现的映射

- `kbMode`/`wikiConfig`/`graphSchema`：`app/schemas/knowledge_base.py` 的 create/update 请求模型与 `KnowledgeBaseRecord`；`app/services/knowledge_base.py` 校验（枚举/结构，沿用 `100001`）；
- `productType`/`wikiStrategy`/`graphStrategy`：`app/schemas/parse.py` 校验扩展；`parse`/`parse-direct`/`ingest-and-parse` 任务联动库形态；
- 库级访问接口：`app/routers/knowledge_base.py` 新增 `wiki/*`、`graph/*` 只读路由，权限沿用库维度；`app/core/catalog.py` 在「知识库」类别登记（不新增分类）；
- 错误码：可复用 `100001`/`100404`/`100403`；如需形态冲突专用码，新增 `200014`（库形态冲突，进 registry）；
- 免库场景：`parse-direct` 支持 `productType=wiki|graph`，图谱仅 `graphScope=doc`，产物查询仍走 `parse-result/*`。
