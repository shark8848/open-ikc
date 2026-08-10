package io.openikc.sdk;

import java.security.SecureRandom;

/**
 * 23 位纯数字 traceId：13 位毫秒时间戳 + 10 位随机数（对齐 Python SDK）。
 */
public final class TraceId {

    private static final SecureRandom RANDOM = new SecureRandom();
    private static final int TRACE_ID_DIGITS = 23;

    private TraceId() {
    }

    /** 生成新的 23 位纯数字 traceId。 */
    public static String generate() {
        long timestampMs = System.currentTimeMillis();
        long randomDigits = RANDOM.nextLong(0L, 10_000_000_000L); // 10 位随机
        String ts = String.format("%013d", timestampMs);
        String rand = String.format("%010d", randomDigits);
        return ts + rand;
    }

    /** 校验是否为 23 位纯数字。 */
    public static boolean isValid(String traceId) {
        if (traceId == null || traceId.length() != TRACE_ID_DIGITS) {
            return false;
        }
        for (int i = 0; i < traceId.length(); i++) {
            char c = traceId.charAt(i);
            if (c < '0' || c > '9') {
                return false;
            }
        }
        return true;
    }
}
