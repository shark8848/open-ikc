package io.openikc.sdk;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 统一响应壳：errCode / errMsg / data / traceId（对齐 Python Envelope）。
 */
public final class Envelope {

    public static final String SUCCESS_CODE = "000000";

    private final String errCode;
    private final String errMsg;
    private final Map<String, Object> data;
    private final String traceId;

    public Envelope(String errCode, String errMsg, Map<String, Object> data, String traceId) {
        this.errCode = errCode == null ? "" : errCode;
        this.errMsg = errMsg == null ? "" : errMsg;
        this.data = data == null ? new LinkedHashMap<>() : data;
        this.traceId = traceId == null ? "" : traceId;
    }

    public String getErrCode() {
        return errCode;
    }

    public String getErrMsg() {
        return errMsg;
    }

    public Map<String, Object> getData() {
        return data;
    }

    public String getTraceId() {
        return traceId;
    }

    public boolean isOk() {
        return SUCCESS_CODE.equals(errCode);
    }
}
