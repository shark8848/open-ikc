package io.openikc.sdk;

import org.junit.jupiter.api.Test;

import java.util.HashSet;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class TraceIdTest {

    @Test
    void generatedTraceIdHas23Digits() {
        String id = TraceId.generate();
        assertEquals(23, id.length(), "traceId 应为 23 位");
        assertTrue(id.chars().allMatch(c -> c >= '0' && c <= '9'), "应为纯数字");
    }

    @Test
    void generatedTraceIdsAreUnique() {
        Set<String> seen = new HashSet<>();
        for (int i = 0; i < 1000; i++) {
            seen.add(TraceId.generate());
        }
        assertEquals(1000, seen.size(), "1000 次生成应无重复");
    }

    @Test
    void isValidRejectsBadValues() {
        assertTrue(TraceId.isValid(TraceId.generate()));
        assertFalse(TraceId.isValid(null));
        assertFalse(TraceId.isValid(""));
        assertFalse(TraceId.isValid("123"));
        assertFalse(TraceId.isValid("1234567890123456789012a"));
        assertFalse(TraceId.isValid("123456789012345678901234"));
    }

    @Test
    void timestampPrefixIsRecent() {
        String id = TraceId.generate();
        long ts = Long.parseLong(id.substring(0, 13));
        long now = System.currentTimeMillis();
        assertTrue(Math.abs(now - ts) < 60_000, "13 位毫秒时间戳应与当前时间接近");
    }
}
