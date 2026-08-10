package io.openikc.sdk;

import com.sun.net.httpserver.HttpServer;
import io.openikc.sdk.model.Documents;
import io.openikc.sdk.model.KnowledgeBase;
import io.openikc.sdk.model.Parse;
import io.openikc.sdk.model.Search;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * OpenIKCClient 集成测试：JDK 内嵌 HttpServer mock 平台。
 */
class OpenIKCClientTest {

    private HttpServer server;
    private String baseUrl;
    private final AtomicReference<String> lastAuthorization = new AtomicReference<>();
    private final AtomicReference<String> lastUserId = new AtomicReference<>();
    private final AtomicReference<String> lastTraceId = new AtomicReference<>();

    @BeforeEach
    void setUp() throws IOException {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.start();
        baseUrl = "http://127.0.0.1:" + server.getAddress().getPort();
    }

    @AfterEach
    void tearDown() {
        server.stop(0);
    }

    private void handle(String path, String method, String responseJson, int status) {
        server.createContext(path, exchange -> {
            lastAuthorization.set(exchange.getRequestHeaders().getFirst("Authorization"));
            lastUserId.set(exchange.getRequestHeaders().getFirst("X-User-Id"));
            lastTraceId.set(exchange.getRequestHeaders().getFirst("X-Trace-Id"));
            byte[] body = responseJson.getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().set("Content-Type", "application/json");
            exchange.sendResponseHeaders(status, body.length);
            try (OutputStream os = exchange.getResponseBody()) {
                os.write(body);
            }
        });
    }

    // ---------- 知识库 ----------

    @Test
    void knowledgeBaseCreateParsesEnvelope() {
        handle("/api/v1/knowledge-bases/create", "POST",
                "{\"errCode\":\"000000\",\"errMsg\":\"success\",\"data\":"
                        + "{\"kbId\":\"kb-100\",\"kbName\":\"测试库\",\"kbType\":\"personal\"},\"traceId\":\"t-1\"}",
                200);
        try (OpenIKCClient client = new OpenIKCClient.Builder(baseUrl).token("secret").build()) {
            KnowledgeBase kb = client.knowledgeBases().create("测试库", null, null, null,
                    null, null, null, null);
            assertEquals("kb-100", kb.getKbId());
            assertEquals("测试库", kb.getKbName());
            assertEquals("personal", kb.getKbType());
        }
    }

    @Test
    void knowledgeBaseGetUsesPathParam() {
        handle("/api/v1/knowledge-bases/kb-42", "GET",
                "{\"errCode\":\"000000\",\"errMsg\":\"success\",\"data\":{\"kbId\":\"kb-42\"},\"traceId\":\"t\"}",
                200);
        try (OpenIKCClient client = new OpenIKCClient.Builder(baseUrl).build()) {
            KnowledgeBase kb = client.knowledgeBases().queryGet("kb-42");
            assertEquals("kb-42", kb.getKbId());
        }
    }

    @Test
    void knowledgeBaseQueryParsesPage() {
        handle("/api/v1/knowledge-bases/query", "POST",
                "{\"errCode\":\"000000\",\"errMsg\":\"success\",\"data\":{\"total\":2,\"page\":1,\"pageSize\":20,"
                        + "\"items\":[{\"kbId\":\"kb-1\",\"kbName\":\"A\"},{\"kbId\":\"kb-2\",\"kbName\":\"B\"}]},\"traceId\":\"t\"}",
                200);
        try (OpenIKCClient client = new OpenIKCClient.Builder(baseUrl).build()) {
            KnowledgeBase.KnowledgeBasePage page = client.knowledgeBases().query(1, 20, null,
                    null, null, null, null);
            assertEquals(2, page.getTotal());
            assertEquals(2, page.getItems().size());
            assertEquals("kb-2", page.getItems().get(1).getKbId());
        }
    }

    // ---------- 错误映射 ----------

    @Test
    void businessErrorMapsToUnauthorizedException() {
        handle("/api/v1/knowledge-bases/query", "POST",
                "{\"errCode\":\"100401\",\"errMsg\":\"未认证或认证失败\",\"data\":{},\"traceId\":\"t-401\"}",
                200);
        try (OpenIKCClient client = new OpenIKCClient.Builder(baseUrl).build()) {
            OpenIKCApiException exc = assertThrows(OpenIKCApiException.class,
                    () -> client.knowledgeBases().query(1, 20, null, null, null, null, null));
            assertInstanceOf(ApiExceptions.UnauthorizedException.class, exc);
            assertEquals("100401", exc.getErrCode());
            assertEquals("t-401", exc.getTraceId());
        }
    }

    @Test
    void businessErrorMapsToValidationException() {
        handle("/api/v1/knowledge-bases/query", "POST",
                "{\"errCode\":\"100001\",\"errMsg\":\"参数错误\",\"data\":{},\"traceId\":\"t\"}",
                200);
        try (OpenIKCClient client = new OpenIKCClient.Builder(baseUrl).build()) {
            assertThrows(ApiExceptions.ValidationException.class,
                    () -> client.knowledgeBases().query(1, 20, null, null, null, null, null));
        }
    }

    @Test
    void unknownErrorCodeMapsToBusinessException() {
        handle("/api/v1/knowledge-bases/query", "POST",
                "{\"errCode\":\"200001\",\"errMsg\":\"解析失败\",\"data\":{},\"traceId\":\"t\"}",
                200);
        try (OpenIKCClient client = new OpenIKCClient.Builder(baseUrl).build()) {
            assertThrows(ApiExceptions.BusinessException.class,
                    () -> client.knowledgeBases().query(1, 20, null, null, null, null, null));
        }
    }

    @Test
    void rawReturnsEnvelopeWithoutThrowing() {
        handle("/api/v1/knowledge-bases/query", "POST",
                "{\"errCode\":\"100403\",\"errMsg\":\"无权限\",\"data\":{},\"traceId\":\"t\"}",
                200);
        try (OpenIKCClient client = new OpenIKCClient.Builder(baseUrl).build()) {
            Envelope env = client.raw("POST", "/api/v1/knowledge-bases/query", null, null,
                    Map.of("page", 1, "pageSize", 20));
            assertFalse(env.isOk());
            assertEquals("100403", env.getErrCode());
        }
    }

    @Test
    void httpErrorWithoutEnvelopeThrowsProtocolException() {
        handle("/api/v1/knowledge-bases/query", "POST", "Internal Server Error", 500);
        try (OpenIKCClient client = new OpenIKCClient.Builder(baseUrl).build()) {
            assertThrows(OpenIKCProtocolException.class,
                    () -> client.knowledgeBases().query(1, 20, null, null, null, null, null));
        }
    }

    // ---------- 请求头透传 ----------

    @Test
    void sendsAuthAndIdentityHeaders() {
        handle("/api/v1/knowledge-bases/query", "POST",
                "{\"errCode\":\"000000\",\"errMsg\":\"success\",\"data\":{\"total\":0,\"page\":1,\"pageSize\":20,\"items\":[]},\"traceId\":\"t\"}",
                200);
        CallerIdentity identity = CallerIdentity.builder()
                .userId("u-1")
                .tenantId("t-1")
                .roles(List.of("admin", "ops"))
                .permissions(List.of("kb:read"))
                .build();
        try (OpenIKCClient client = new OpenIKCClient.Builder(baseUrl)
                .token("tok-123")
                .identity(identity)
                .build()) {
            client.knowledgeBases().query(1, 20, null, null, null, null, null);
        }
        assertEquals("Bearer tok-123", lastAuthorization.get());
        assertEquals("u-1", lastUserId.get());
        assertTrue(TraceId.isValid(lastTraceId.get()), "应自动生成 23 位 traceId 头");
    }

    // ---------- 系统路由 ----------

    @Test
    void fetchCatalogParsesDataList() {
        handle("/api/catalog", "GET",
                "{\"status\":true,\"data\":[{\"category\":\"知识库\"},{\"category\":\"检索\"}]}",
                200);
        try (OpenIKCClient client = new OpenIKCClient.Builder(baseUrl).build()) {
            List<Map<String, Object>> catalog = client.fetchCatalog();
            assertEquals(2, catalog.size());
            assertEquals("知识库", catalog.get(0).get("category"));
        }
    }

    // ---------- 文档 / 解析 / 检索 ----------

    @Test
    void documentIngestParsesResult() {
        handle("/api/v1/knowledge-documents/ingest", "POST",
                "{\"errCode\":\"000000\",\"errMsg\":\"success\",\"data\":"
                        + "{\"ingestTaskId\":\"it-1\",\"taskStatus\":\"RUNNING\",\"sourceType\":\"file\",\"ingestTime\":\"2026-08-10\",\"docIds\":[\"d-1\"]},\"traceId\":\"t\"}",
                200);
        try (OpenIKCClient client = new OpenIKCClient.Builder(baseUrl).build()) {
            Documents.DocumentIngestResult result = client.documents().ingest(
                    "kb-1", Map.of("type", "file", "url", "https://x/a.pdf"), null,
                    null, null, null, null, null, null);
            assertEquals("it-1", result.getIngestTaskId());
            assertEquals(List.of("d-1"), result.getDocIds());
        }
    }

    @Test
    void parseQueryResultParses() {
        handle("/api/v1/knowledge-documents/parse-result/query", "GET",
                "{\"errCode\":\"000000\",\"errMsg\":\"success\",\"data\":"
                        + "{\"parseStatus\":\"SUCCESS\",\"pageCount\":3,\"chunkCount\":10},\"traceId\":\"t\"}",
                200);
        try (OpenIKCClient client = new OpenIKCClient.Builder(baseUrl).build()) {
            Parse.ParseResult result = client.parse().queryResult("d-1");
            assertEquals("SUCCESS", result.getParseStatus());
            assertEquals(3, result.getPageCount());
            assertEquals(10, result.getChunkCount());
        }
    }

    @Test
    void searchQueryParsesResults() {
        handle("/api/v1/knowledge-search/query", "POST",
                "{\"errCode\":\"000000\",\"errMsg\":\"success\",\"data\":"
                        + "{\"answer\":\"答案\",\"results\":[{\"docId\":\"d-1\",\"score\":0.85,\"snippet\":\"片段\"}]},\"traceId\":\"t\"}",
                200);
        try (OpenIKCClient client = new OpenIKCClient.Builder(baseUrl).build()) {
            Search.SearchResult result = client.search().query("问题", "kb-1", null, null, null);
            assertEquals("答案", result.getAnswer());
            assertEquals(1, result.getResults().size());
            assertEquals(0.85, result.getResults().get(0).getScore(), 1e-9);
            assertEquals("片段", result.getResults().get(0).getSnippet());
        }
    }

    // ---------- 回归：真实平台 HTTP/1.1 兼容性 ----------

    /**
     * 回归保护：平台 uvicorn/h11 不支持 HTTP/2 h2c 升级，会以「Upgrade 头 → 400 拒绝」。
     * JDK HttpClient 默认发送 h2c 升级头，SDK 必须显式固定 HTTP/1.1。
     * 模拟 h11：mock 服务发现 Upgrade: h2c 头时返回 400（同真实平台 Invalid HTTP request received.）。
     */
    @Test
    void doesNotSendH2CUpgradeHeader() {
        server.createContext("/api/v1/knowledge-bases/kb-1", exchange -> {
            String upgrade = exchange.getRequestHeaders().getFirst("Upgrade");
            String body;
            int status;
            if (upgrade != null && upgrade.contains("h2c")) {
                // 模拟 uvicorn/h11 拒绝 h2c 升级
                status = 400;
                body = "Invalid HTTP request received.";
            } else {
                status = 200;
                body = "{\"errCode\":\"000000\",\"errMsg\":\"success\",\"data\":{\"kbId\":\"kb-1\"},\"traceId\":\"t\"}";
            }
            byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().set("Content-Type", "application/json");
            exchange.sendResponseHeaders(status, bytes.length);
            try (OutputStream os = exchange.getResponseBody()) {
                os.write(bytes);
            }
        });
        try (OpenIKCClient client = new OpenIKCClient.Builder(baseUrl).token("t").build()) {
            // 若 SDK 发送 h2c 升级头，这里会收到 400 → OpenIKCProtocolException；
            // 正确固定 HTTP/1.1 时返回 200 并正常解析。
            KnowledgeBase kb = client.knowledgeBases().queryGet("kb-1");
            assertEquals("kb-1", kb.getKbId());
        }
    }
}
