package io.openikc.sdk.internal;

import io.openikc.sdk.ApiExceptions;
import io.openikc.sdk.CallerIdentity;
import io.openikc.sdk.Envelope;
import io.openikc.sdk.OpenIKCApiException;
import io.openikc.sdk.OpenIKCConnectionException;
import io.openikc.sdk.OpenIKCProtocolException;
import io.openikc.sdk.OpenIKCTimeoutException;
import io.openikc.sdk.TraceId;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ThreadLocalRandom;

/**
 * 同步 HTTP 传输：超时、重试、统一壳解析与异常映射（对齐 Python transport.py）。
 *
 * <p>使用 JDK {@link java.net.http.HttpClient}，零第三方依赖。
 */
public final class Transport {

    private static final Set<Integer> RETRYABLE_STATUS_CODES = Set.of(502, 503, 504);
    private static final Duration DEFAULT_CONNECT_TIMEOUT = Duration.ofSeconds(5);
    private static final Duration DEFAULT_READ_TIMEOUT = Duration.ofSeconds(60);

    private final String baseUrl;
    private final String token;
    private final int maxRetries;
    private final CallerIdentity identity;
    private final Map<String, String> extraHeaders;
    private final String fixedTraceId;
    private final HttpClient client;

    public Transport(String baseUrl, String token, Integer timeoutSeconds, Integer maxRetries,
                     CallerIdentity identity, Map<String, String> extraHeaders, String traceId) {
        this.baseUrl = baseUrl == null ? "" : baseUrl.replaceAll("/+$", "");
        this.token = token;
        this.maxRetries = maxRetries == null ? 2 : Math.max(0, maxRetries);
        this.identity = identity;
        this.extraHeaders = extraHeaders == null ? new LinkedHashMap<>() : new LinkedHashMap<>(extraHeaders);
        this.fixedTraceId = traceId;
        Duration readTimeout = timeoutSeconds != null && timeoutSeconds > 0
                ? Duration.ofSeconds(timeoutSeconds)
                : DEFAULT_READ_TIMEOUT;
        this.client = HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_1_1) // uvicorn/h11 不支持 HTTP/2 h2c 升级，必须显式固定 HTTP/1.1
                .connectTimeout(DEFAULT_CONNECT_TIMEOUT)
                .followRedirects(HttpClient.Redirect.NEVER)
                .build();
        this.readTimeout = readTimeout;
    }

    private final Duration readTimeout;

    public String getBaseUrl() {
        return baseUrl;
    }

    public boolean hasToken() {
        return token != null && !token.isEmpty();
    }

    /** 业务请求：errCode != 000000 时抛对应异常；raiseForError=false 时返回原始壳。 */
    public Envelope request(String method, String path, Map<String, String> pathParams,
                            Map<String, Object> queryParams, Map<String, Object> body,
                            boolean raiseForError) {
        String url = buildUrl(baseUrl, path, pathParams, queryParams);
        String traceId = resolveTraceId();
        Map<String, String> headers = HeaderBuilder.build(token, traceId, identity, extraHeaders);
        HttpResponse<String> response = send(method, url, body, headers, traceId);
        return handleResponse(response, traceId, raiseForError);
    }

    /** 系统路由（/api/catalog、/api/error-codes）：返回解析后的 JSON 对象。 */
    public Object getJson(String path) {
        String url = baseUrl + path;
        String traceId = resolveTraceId();
        Map<String, String> headers = HeaderBuilder.build(token, traceId, identity, extraHeaders);
        HttpResponse<String> response = send("GET", url, null, headers, traceId);
        if (response.statusCode() >= 400) {
            throw new OpenIKCProtocolException(
                    "HTTP " + response.statusCode() + ": GET " + url,
                    response.statusCode(), response.body(), traceId);
        }
        try {
            return Json.parse(response.body());
        } catch (IllegalArgumentException exc) {
            throw new OpenIKCProtocolException(
                    "HTTP " + response.statusCode() + " 响应不是合法 JSON",
                    response.statusCode(), response.body(), traceId);
        }
    }

    private String resolveTraceId() {
        if (fixedTraceId != null && !fixedTraceId.isEmpty()) {
            return fixedTraceId;
        }
        return TraceId.generate();
    }

    private static String buildUrl(String baseUrl, String path, Map<String, String> pathParams,
                                   Map<String, Object> queryParams) {
        String resolved = path;
        if (pathParams != null) {
            for (Map.Entry<String, String> e : pathParams.entrySet()) {
                resolved = resolved.replace("{" + e.getKey() + "}", String.valueOf(e.getValue()));
            }
        }
        StringBuilder sb = new StringBuilder(baseUrl).append(resolved);
        if (queryParams != null && !queryParams.isEmpty()) {
            sb.append('?');
            boolean first = true;
            for (Map.Entry<String, Object> e : queryParams.entrySet()) {
                if (!first) {
                    sb.append('&');
                }
                first = false;
                sb.append(e.getKey()).append('=').append(urlEncode(String.valueOf(e.getValue())));
            }
        }
        return sb.toString();
    }

    private static String urlEncode(String value) {
        return java.net.URLEncoder.encode(value, java.nio.charset.StandardCharsets.UTF_8)
                .replace("+", "%20");
    }

    private HttpResponse<String> send(String method, String url, Map<String, Object> body,
                                      Map<String, String> headers, String traceId) {
        for (int attempt = 0; attempt <= maxRetries; attempt++) {
            try {
                HttpRequest.Builder builder = HttpRequest.newBuilder()
                        .uri(URI.create(url))
                        .timeout(readTimeout);
                HeaderBuilder.apply(builder, headers);
                if (body != null && !body.isEmpty()) {
                    String json = JsonWriter.write(body);
                    builder.header("Content-Type", "application/json");
                    switch (method) {
                        case "POST" -> builder.POST(HttpRequest.BodyPublishers.ofString(json));
                        case "PUT" -> builder.PUT(HttpRequest.BodyPublishers.ofString(json));
                        case "PATCH" -> builder.method("PATCH", HttpRequest.BodyPublishers.ofString(json));
                        default -> throw new OpenIKCConnectionException("不支持的请求方法: " + method, traceId);
                    }
                } else {
                    switch (method) {
                        case "GET" -> builder.GET();
                        case "POST" -> builder.POST(HttpRequest.BodyPublishers.noBody());
                        case "PUT" -> builder.PUT(HttpRequest.BodyPublishers.noBody());
                        case "DELETE" -> builder.DELETE();
                        default -> throw new OpenIKCConnectionException("不支持的请求方法: " + method, traceId);
                    }
                }
                HttpResponse<String> response = client.send(builder.build(),
                        HttpResponse.BodyHandlers.ofString());
                if (RETRYABLE_STATUS_CODES.contains(response.statusCode()) && attempt < maxRetries
                        && canRetry(method, body)) {
                    sleepBackoff(attempt);
                    continue;
                }
                return response;
            } catch (java.net.http.HttpTimeoutException exc) {
                if (!canRetry(method, body) || attempt >= maxRetries) {
                    throw new OpenIKCTimeoutException("请求超时: " + method + " " + url, traceId);
                }
                sleepBackoff(attempt);
            } catch (IOException exc) {
                if (!canRetry(method, body) || attempt >= maxRetries) {
                    throw new OpenIKCConnectionException("连接失败: " + method + " " + url + ": " + exc.getMessage(), traceId);
                }
                sleepBackoff(attempt);
            } catch (InterruptedException exc) {
                Thread.currentThread().interrupt();
                throw new OpenIKCConnectionException("请求被中断: " + method + " " + url, traceId);
            }
        }
        throw new OpenIKCConnectionException("重试耗尽: " + method + " " + url, traceId);
    }

    private static boolean canRetry(String method, Map<String, Object> body) {
        String upper = method.toUpperCase();
        if (upper.equals("GET") || upper.equals("HEAD") || upper.equals("OPTIONS")) {
            return true;
        }
        if (upper.equals("POST")) {
            return body != null && body.containsKey("reqId");
        }
        return false;
    }

    private static void sleepBackoff(int attempt) {
        long delayMillis = Math.min((long) (500 * Math.pow(2, attempt)), 4000) + ThreadLocalRandom.current().nextInt(0, 200);
        try {
            Thread.sleep(delayMillis);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    private static Envelope handleResponse(HttpResponse<String> response, String traceId, boolean raiseForError) {
        String text = response.body();
        if (response.statusCode() >= 400) {
            try {
                Envelope envelope = EnvelopeParser.parse(text, traceId);
                if (raiseForError) {
                    throw apiError(envelope);
                }
                return envelope;
            } catch (OpenIKCProtocolException e) {
                throw new OpenIKCProtocolException(
                        "HTTP " + response.statusCode() + " 且响应不符合统一响应壳协议",
                        response.statusCode(), text, traceId);
            }
        }
        Envelope envelope;
        try {
            envelope = EnvelopeParser.parse(text, traceId);
        } catch (OpenIKCProtocolException e) {
            throw new OpenIKCProtocolException(
                    "HTTP " + response.statusCode() + " 响应不符合统一响应壳协议",
                    response.statusCode(), text, traceId);
        }
        if (raiseForError && !envelope.isOk()) {
            throw apiError(envelope);
        }
        return envelope;
    }

    private static OpenIKCApiException apiError(Envelope envelope) {
        String traceId = envelope.getTraceId();
        return ApiExceptions.fromCode(envelope.getErrCode(), envelope.getErrMsg(), traceId);
    }
}
