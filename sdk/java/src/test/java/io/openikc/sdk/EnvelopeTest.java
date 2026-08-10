package io.openikc.sdk;

import io.openikc.sdk.internal.EnvelopeParser;
import io.openikc.sdk.internal.Json;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class EnvelopeTest {

    @Test
    void parsesSuccessEnvelope() {
        Envelope env = EnvelopeParser.parse(
                "{\"errCode\":\"000000\",\"errMsg\":\"success\",\"data\":{\"kbId\":\"kb-1\"},\"traceId\":\"123\"}",
                "req-trace");
        assertTrue(env.isOk());
        assertEquals("000000", env.getErrCode());
        assertEquals("success", env.getErrMsg());
        assertEquals("kb-1", env.getData().get("kbId"));
        assertEquals("123", env.getTraceId());
    }

    @Test
    void parsesBusinessErrorEnvelope() {
        Envelope env = EnvelopeParser.parse(
                "{\"errCode\":\"100401\",\"errMsg\":\"未认证或认证失败\",\"data\":{},\"traceId\":\"abc\"}",
                "req-trace");
        assertFalse(env.isOk());
        assertEquals("100401", env.getErrCode());
    }

    @Test
    void parsesNullDataAsEmptyMap() {
        Envelope env = EnvelopeParser.parse(
                "{\"errCode\":\"000000\",\"errMsg\":\"success\",\"data\":null,\"traceId\":\"\"}",
                "req-trace");
        assertTrue(env.isOk());
        assertTrue(env.getData().isEmpty());
    }

    @Test
    void rejectsNonJson() {
        assertThrows(OpenIKCProtocolException.class,
                () -> EnvelopeParser.parse("not-json", "req-trace"));
    }

    @Test
    void rejectsMissingErrCode() {
        assertThrows(OpenIKCProtocolException.class,
                () -> EnvelopeParser.parse("{\"data\":{}}", "req-trace"));
    }

    @Test
    void jsonParserHandlesNestedStructures() {
        Map<String, Object> obj = Json.parseObject(
                "{\"a\":1,\"b\":\"x\\ny\",\"c\":[true,false,null,{\"d\":1.5}],\"e\":{\"f\":\"g\"}}");
        assertEquals(1L, obj.get("a"));
        assertEquals("x\ny", obj.get("b"));
        Object c = obj.get("c");
        assertTrue(c instanceof List);
        List<?> list = (List<?>) c;
        assertEquals(Boolean.TRUE, list.get(0));
        assertEquals(Boolean.FALSE, list.get(1));
        assertEquals(null, list.get(2));
        assertEquals(1.5, list.get(3) instanceof Map m ? m.get("d") : null);
        assertEquals("g", ((Map<?, ?>) obj.get("e")).get("f"));
    }

    @Test
    void jsonWriterSerializesRequestBody() {
        Map<String, Object> body = new java.util.LinkedHashMap<>();
        body.put("kbName", "测试 库");
        body.put("page", 1);
        body.put("enabled", true);
        body.put("tags", List.of("a", "b"));
        body.put("nested", Map.of("k", "v"));
        body.put("nothing", null);
        String json = io.openikc.sdk.internal.JsonWriter.write(body);
        Map<String, Object> roundTrip = Json.parseObject(json);
        assertEquals("测试 库", roundTrip.get("kbName"));
        assertEquals(1L, roundTrip.get("page"));
        assertEquals(Boolean.TRUE, roundTrip.get("enabled"));
        assertEquals(List.of("a", "b"), roundTrip.get("tags"));
        assertEquals(Map.of("k", "v"), roundTrip.get("nested"));
        assertTrue(roundTrip.containsKey("nothing"));
        assertEquals(null, roundTrip.get("nothing"));
    }
}
