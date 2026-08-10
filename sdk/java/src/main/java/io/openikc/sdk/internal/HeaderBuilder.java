package io.openikc.sdk.internal;

import io.openikc.sdk.CallerIdentity;

import java.net.http.HttpRequest;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 请求头构建（对齐 Python headers.build_headers）。
 */
public final class HeaderBuilder {

    public static final String SDK_VERSION = "1.0.0";

    private HeaderBuilder() {
    }

    /**
     * 构建请求头：认证、trace 与 AUTHZ 身份头；extraHeaders 优先级最高。
     */
    public static Map<String, String> build(
            String token,
            String traceId,
            CallerIdentity identity,
            Map<String, String> extraHeaders
    ) {
        Map<String, String> headers = new LinkedHashMap<>();
        headers.put("Accept", "application/json");
        headers.put("User-Agent", "open-ikc-sdk/" + SDK_VERSION);
        headers.put("X-Request-Id", traceId);
        headers.put("X-Trace-Id", traceId);
        if (token != null && !token.isEmpty()) {
            headers.put("Authorization", "Bearer " + token);
        }
        if (identity != null) {
            putIfNotBlank(headers, "X-User-Id", identity.getUserId());
            putIfNotBlank(headers, "X-Tenant-Id", identity.getTenantId());
            putIfNotBlank(headers, "X-User-Roles", join(identity.getRoles()));
            putIfNotBlank(headers, "X-User-Permissions", join(identity.getPermissions()));
            putIfNotBlank(headers, "X-User-Deny-Permissions", join(identity.getDenyPermissions()));
            putIfNotBlank(headers, "X-Auth-System", identity.getAuthSystem());
        }
        if (extraHeaders != null) {
            headers.putAll(extraHeaders);
        }
        return headers;
    }

    private static void putIfNotBlank(Map<String, String> headers, String key, String value) {
        if (value != null && !value.isBlank()) {
            headers.put(key, value);
        }
    }

    private static String join(java.util.List<String> items) {
        if (items == null || items.isEmpty()) {
            return "";
        }
        return String.join(",", items);
    }

    /** 将 Map 头应用到 HttpRequest.Builder。 */
    public static void apply(HttpRequest.Builder builder, Map<String, String> headers) {
        for (Map.Entry<String, String> e : headers.entrySet()) {
            builder.header(e.getKey(), e.getValue());
        }
    }
}
