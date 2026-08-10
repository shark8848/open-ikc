package io.openikc.sdk;

import io.openikc.sdk.internal.Transport;
import io.openikc.sdk.model.Documents;
import io.openikc.sdk.model.KnowledgeBase;
import io.openikc.sdk.model.Parse;
import io.openikc.sdk.model.Search;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * OpenIKC 开放平台 Java SDK 同步客户端。
 *
 * <p>四类领域方法：知识库 {@link #knowledgeBases()}、文档 {@link #documents()}、
 * 解析 {@link #parse()}、检索 {@link #search()}，对齐 Python SDK。
 *
 * <p>配置：构造器显式参数，或 {@link #fromEnv()} 读取环境变量
 * （OPEN_PLATFORM_BASE_URL / OPEN_PLATFORM_TOKEN / OPEN_PLATFORM_USER_ID / OPEN_PLATFORM_TENANT_ID / OPEN_PLATFORM_ROLES）。
 */
public final class OpenIKCClient implements AutoCloseable {

    private final Transport transport;

    private final KnowledgeBaseClient knowledgeBases;
    private final DocumentClient documents;
    private final ParseClient parse;
    private final SearchClient search;

    public OpenIKCClient(Builder builder) {
        this.transport = new Transport(
                builder.baseUrl,
                builder.token,
                builder.timeoutSeconds,
                builder.maxRetries,
                builder.identity,
                builder.extraHeaders,
                builder.traceId);
        this.knowledgeBases = new KnowledgeBaseClient(this);
        this.documents = new DocumentClient(this);
        this.parse = new ParseClient(this);
        this.search = new SearchClient(this);
    }

    /** 从环境变量构建客户端（OPEN_PLATFORM_BASE_URL / TOKEN / USER_ID / TENANT_ID / ROLES）。 */
    public static OpenIKCClient fromEnv() {
        String baseUrl = envOr("OPEN_PLATFORM_BASE_URL", "http://127.0.0.1:18000");
        String token = System.getenv("OPEN_PLATFORM_TOKEN");
        if ((token == null || token.isEmpty()) && System.getenv("OPEN_PLATFORM_TOKENS") != null) {
            String tokens = System.getenv("OPEN_PLATFORM_TOKENS");
            if (tokens != null && !tokens.isBlank()) {
                token = tokens.split(",")[0].trim();
            }
        }
        CallerIdentity.Builder identity = CallerIdentity.builder();
        String userId = System.getenv("OPEN_PLATFORM_USER_ID");
        String tenantId = System.getenv("OPEN_PLATFORM_TENANT_ID");
        String roles = System.getenv("OPEN_PLATFORM_ROLES");
        if (userId != null && !userId.isEmpty()) {
            identity.userId(userId);
        }
        if (tenantId != null && !tenantId.isEmpty()) {
            identity.tenantId(tenantId);
        }
        if (roles != null && !roles.isBlank()) {
            identity.roles(java.util.Arrays.stream(roles.split(","))
                    .map(String::trim)
                    .filter(s -> !s.isEmpty())
                    .toList());
        }
        return new OpenIKCClient.Builder(baseUrl)
                .token(token)
                .identity(identity.build())
                .build();
    }

    private static String envOr(String key, String def) {
        String v = System.getenv(key);
        return (v == null || v.isEmpty()) ? def : v;
    }

    // ---------- 低层调用 ----------

    /** 低层业务调用：errCode != 000000 时抛对应异常。 */
    public Envelope request(String method, String path, Map<String, String> pathParams,
                            Map<String, Object> queryParams, Map<String, Object> body) {
        return transport.request(method, path, pathParams, queryParams, body, true);
    }

    /** 逃生口：返回原始统一响应壳，业务错误码不抛异常。 */
    public Envelope raw(String method, String path, Map<String, String> pathParams,
                        Map<String, Object> queryParams, Map<String, Object> body) {
        return transport.request(method, path, pathParams, queryParams, body, false);
    }

    /** 拉取平台对外 API 目录（/api/catalog）。 */
    @SuppressWarnings("unchecked")
    public List<Map<String, Object>> fetchCatalog() {
        Object json = transport.getJson("/api/catalog");
        if (json instanceof Map<?, ?> map && map.get("data") instanceof List<?> list) {
            return (List<Map<String, Object>>) (List<?>) list;
        }
        return List.of();
    }

    /** 拉取平台错误码目录（/api/error-codes）。 */
    @SuppressWarnings("unchecked")
    public List<Map<String, Object>> fetchErrorCodes() {
        Object json = transport.getJson("/api/error-codes");
        if (json instanceof Map<?, ?> map && map.get("data") instanceof List<?> list) {
            return (List<Map<String, Object>>) (List<?>) list;
        }
        return List.of();
    }

    // ---------- 领域客户端 ----------

    public KnowledgeBaseClient knowledgeBases() {
        return knowledgeBases;
    }

    public DocumentClient documents() {
        return documents;
    }

    public ParseClient parse() {
        return parse;
    }

    public SearchClient search() {
        return search;
    }

    @Override
    public void close() {
        // java.net.http.HttpClient 无需显式关闭（JDK 内部管理连接池）
    }

    @Override
    public String toString() {
        return "OpenIKCClient(baseUrl=" + transport.getBaseUrl()
                + ", token=" + (transport.hasToken() ? "<set>" : "None") + ")";
    }

    // ---------- Builder ----------

    public static final class Builder {
        private final String baseUrl;
        private String token;
        private Integer timeoutSeconds;
        private Integer maxRetries = 2;
        private CallerIdentity identity;
        private Map<String, String> extraHeaders;
        private String traceId;

        public Builder(String baseUrl) {
            if (baseUrl == null || baseUrl.isBlank()) {
                throw new IllegalArgumentException("baseUrl 不能为空");
            }
            this.baseUrl = baseUrl;
        }

        public Builder token(String v) {
            this.token = v;
            return this;
        }

        public Builder timeoutSeconds(Integer v) {
            this.timeoutSeconds = v;
            return this;
        }

        public Builder maxRetries(Integer v) {
            this.maxRetries = v;
            return this;
        }

        public Builder identity(CallerIdentity v) {
            this.identity = v;
            return this;
        }

        public Builder extraHeaders(Map<String, String> v) {
            this.extraHeaders = v;
            return this;
        }

        public Builder traceId(String v) {
            this.traceId = v;
            return this;
        }

        public OpenIKCClient build() {
            return new OpenIKCClient(this);
        }
    }

    // ---------- 知识库域 ----------

    public static final class KnowledgeBaseClient {
        private static final java.util.Set<String> UPDATE_FIELDS = java.util.Set.of(
                "kbName", "kbType", "teamId", "orgId", "kbDesc", "visibility", "metadataSchema");

        private final OpenIKCClient client;

        KnowledgeBaseClient(OpenIKCClient client) {
            this.client = client;
        }

        public KnowledgeBase create(String kbName, String kbType, String teamId, String orgId,
                                    String kbDesc, String bizDomain, String visibility,
                                    List<Map<String, Object>> metadataSchema) {
            Map<String, Object> body = new LinkedHashMap<>();
            body.put("kbName", kbName);
            body.put("kbType", kbType == null ? "personal" : kbType);
            body.put("teamId", teamId == null ? "" : teamId);
            body.put("orgId", orgId == null ? "" : orgId);
            body.put("kbDesc", kbDesc == null ? "" : kbDesc);
            body.put("bizDomain", bizDomain == null ? "general" : bizDomain);
            body.put("visibility", visibility == null ? "private" : visibility);
            if (metadataSchema != null) {
                body.put("metadataSchema", metadataSchema);
            }
            Envelope envelope = client.request("POST", "/api/v1/knowledge-bases/create", null, null, body);
            return KnowledgeBase.fromDict(envelope.getData());
        }

        public KnowledgeBase queryGet(String kbId) {
            Envelope envelope = client.request("GET", "/api/v1/knowledge-bases/{kb_id}",
                    Map.of("kb_id", kbId), null, null);
            return KnowledgeBase.fromDict(envelope.getData());
        }

        public KnowledgeBase.KnowledgeBasePage query(int page, int pageSize, String kbType,
                                                     String teamId, String orgId, String ownerId, String keyword) {
            Map<String, Object> body = new LinkedHashMap<>();
            body.put("page", page);
            body.put("pageSize", pageSize);
            if (kbType != null) {
                body.put("kbType", kbType);
            }
            if (teamId != null && !teamId.isEmpty()) {
                body.put("teamId", teamId);
            }
            if (orgId != null && !orgId.isEmpty()) {
                body.put("orgId", orgId);
            }
            if (ownerId != null && !ownerId.isEmpty()) {
                body.put("ownerId", ownerId);
            }
            if (keyword != null && !keyword.isEmpty()) {
                body.put("keyword", keyword);
            }
            Envelope envelope = client.request("POST", "/api/v1/knowledge-bases/query", null, null, body);
            return KnowledgeBase.KnowledgeBasePage.fromDict(envelope.getData());
        }
    }

    // ---------- 文档域 ----------

    public static final class DocumentClient {

        DocumentClient(OpenIKCClient client) {
            this.client = client;
        }

        private final OpenIKCClient client;

        public Documents.DocumentIngestResult ingest(String kbId, Map<String, Object> source,
                                                     String reqId, String teamId, String orgId,
                                                     String docTitle, List<String> tags,
                                                     Map<String, Object> metadata, String orchestrationMode) {
            Map<String, Object> body = new LinkedHashMap<>();
            body.put("kbId", kbId);
            body.put("source", source == null ? Map.of() : source);
            body.put("orchestrationMode", orchestrationMode == null ? "split" : orchestrationMode);
            if (reqId != null && !reqId.isEmpty()) {
                body.put("reqId", reqId);
            }
            if (teamId != null && !teamId.isEmpty()) {
                body.put("teamId", teamId);
            }
            if (orgId != null && !orgId.isEmpty()) {
                body.put("orgId", orgId);
            }
            if (docTitle != null && !docTitle.isEmpty()) {
                body.put("docTitle", docTitle);
            }
            if (tags != null && !tags.isEmpty()) {
                body.put("tags", tags);
            }
            if (metadata != null && !metadata.isEmpty()) {
                body.put("metadata", metadata);
            }
            Envelope envelope = client.request("POST", "/api/v1/knowledge-documents/ingest", null, null, body);
            return Documents.DocumentIngestResult.fromDict(envelope.getData());
        }

        public Documents.DocumentInfo get(String docId) {
            Envelope envelope = client.request("GET", "/api/v1/knowledge-documents/{doc_id}",
                    Map.of("doc_id", docId), null, null);
            return Documents.DocumentInfo.fromDict(envelope.getData());
        }
    }

    // ---------- 解析域 ----------

    public static final class ParseClient {

        ParseClient(OpenIKCClient client) {
            this.client = client;
        }

        private final OpenIKCClient client;

        public Parse.ParseTask parse(String kbId, String docId, String reqId, Map<String, Object> parseStrategy,
                                     Map<String, Object> resultFormat, String executeMode,
                                     String parseMode, String chunkStrategy, Integer chunkSize) {
            Map<String, Object> body = new LinkedHashMap<>();
            body.put("kbId", kbId);
            body.put("docId", docId);
            body.put("executeMode", executeMode == null ? "async" : executeMode);
            if (reqId != null && !reqId.isEmpty()) {
                body.put("reqId", reqId);
            }
            if (parseStrategy != null) {
                body.put("parseStrategy", parseStrategy);
            }
            if (resultFormat != null) {
                body.put("resultFormat", resultFormat);
            }
            if (parseMode != null) {
                body.put("parseMode", parseMode);
            }
            if (chunkStrategy != null) {
                body.put("chunkStrategy", chunkStrategy);
            }
            if (chunkSize != null) {
                body.put("chunkSize", chunkSize);
            }
            Envelope envelope = client.request("POST", "/api/v1/knowledge-documents/parse", null, null, body);
            return Parse.ParseTask.fromDict(envelope.getData());
        }

        public Parse.ParseResult queryResult(String docId) {
            Envelope envelope = client.request("GET", "/api/v1/knowledge-documents/parse-result/query",
                    null, Map.of("docId", docId), null);
            return Parse.ParseResult.fromDict(envelope.getData());
        }

        public Parse.DownloadTicket issueDownloadTicket(String docId) {
            Envelope envelope = client.request("GET", "/api/v1/knowledge-documents/parse-result/issue-download-ticket",
                    null, Map.of("docId", docId), null);
            return Parse.DownloadTicket.fromDict(envelope.getData());
        }
    }

    // ---------- 检索域 ----------

    public static final class SearchClient {

        SearchClient(OpenIKCClient client) {
            this.client = client;
        }

        private final OpenIKCClient client;

        public Search.SearchResult query(String query, String kbId, List<String> kbIds,
                                         String ownerId, String orgPath) {
            Map<String, Object> body = new LinkedHashMap<>();
            if (query != null && !query.isEmpty()) {
                body.put("query", query);
            }
            if (kbId != null && !kbId.isEmpty()) {
                body.put("kbId", kbId);
            }
            if (kbIds != null && !kbIds.isEmpty()) {
                body.put("kbIds", kbIds);
            }
            if (ownerId != null && !ownerId.isEmpty()) {
                body.put("ownerId", ownerId);
            }
            if (orgPath != null && !orgPath.isEmpty()) {
                body.put("orgPath", orgPath);
            }
            Envelope envelope = client.request("POST", "/api/v1/knowledge-search/query", null, null, body);
            return Search.SearchResult.fromDict(envelope.getData());
        }
    }
}
