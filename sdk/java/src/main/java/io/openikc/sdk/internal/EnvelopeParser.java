package io.openikc.sdk.internal;

import io.openikc.sdk.Envelope;
import io.openikc.sdk.OpenIKCProtocolException;

import java.util.Map;

/**
 * 统一响应壳解析（对齐 Python envelope.parse_envelope）。
 */
public final class EnvelopeParser {

    private EnvelopeParser() {
    }

    /**
     * 解析统一响应壳；不符合协议时抛 OpenIKCProtocolException。
     *
     * @param text    原始响应文本
     * @param traceId 请求 traceId（异常时透传）
     */
    public static Envelope parse(String text, String traceId) {
        if (text == null || text.isBlank()) {
            throw new OpenIKCProtocolException("响应为空，不符合统一响应壳协议", traceId);
        }
        Map<String, Object> payload;
        try {
            Object parsed = Json.parse(text);
            if (!(parsed instanceof Map)) {
                throw new OpenIKCProtocolException("响应不是合法 JSON 对象，不符合统一响应壳协议", traceId);
            }
            payload = (Map<String, Object>) parsed;
        } catch (IllegalArgumentException exc) {
            throw new OpenIKCProtocolException("响应不是合法 JSON，不符合统一响应壳协议: " + exc.getMessage(), traceId);
        }
        if (!payload.containsKey("errCode")) {
            throw new OpenIKCProtocolException("响应缺少 errCode，不符合统一响应壳协议", traceId);
        }
        Object data = payload.get("data");
        String errCode = String.valueOf(payload.getOrDefault("errCode", ""));
        String errMsg = String.valueOf(payload.getOrDefault("errMsg", ""));
        String respTraceId = String.valueOf(payload.getOrDefault("traceId", ""));
        Map<String, Object> dataMap = data instanceof Map ? (Map<String, Object>) data : new java.util.LinkedHashMap<>();
        return new Envelope(errCode, errMsg, dataMap, respTraceId);
    }
}
