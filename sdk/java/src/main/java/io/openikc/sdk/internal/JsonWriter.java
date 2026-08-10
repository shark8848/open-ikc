package io.openikc.sdk.internal;

import java.util.List;
import java.util.Map;

/**
 * 极简 JSON 序列化器（仅需序列化请求体：对象/数组/字符串/数字/布尔/null）。
 */
public final class JsonWriter {

    private JsonWriter() {
    }

    public static String write(Object value) {
        StringBuilder sb = new StringBuilder();
        appendValue(sb, value);
        return sb.toString();
    }

    private static void appendValue(StringBuilder sb, Object value) {
        if (value == null) {
            sb.append("null");
        } else if (value instanceof String) {
            sb.append(Json.quote((String) value));
        } else if (value instanceof Boolean || value instanceof Number) {
            sb.append(value);
        } else if (value instanceof Map) {
            appendMap(sb, (Map<?, ?>) value);
        } else if (value instanceof List || value instanceof Iterable) {
            appendArray(sb, (Iterable<?>) value);
        } else {
            // 兜底：对象按 toString（不常见）
            sb.append(Json.quote(String.valueOf(value)));
        }
    }

    private static void appendMap(StringBuilder sb, Map<?, ?> map) {
        sb.append('{');
        boolean first = true;
        for (Map.Entry<?, ?> e : map.entrySet()) {
            if (!first) {
                sb.append(',');
            }
            first = false;
            sb.append(Json.quote(String.valueOf(e.getKey()))).append(':');
            appendValue(sb, e.getValue());
        }
        sb.append('}');
    }

    private static void appendArray(StringBuilder sb, Iterable<?> items) {
        sb.append('[');
        boolean first = true;
        for (Object item : items) {
            if (!first) {
                sb.append(',');
            }
            first = false;
            appendValue(sb, item);
        }
        sb.append(']');
    }
}
