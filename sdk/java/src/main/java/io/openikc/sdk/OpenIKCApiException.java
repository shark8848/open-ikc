package io.openikc.sdk;

/**
 * 平台返回统一响应壳但 errCode != 000000（对齐 Python OpenIKCAPIError）。
 */
public class OpenIKCApiException extends OpenIKCError {

    private final String errCode;
    private final String errMsg;
    private final String traceId;

    public OpenIKCApiException(String message, String errCode, String errMsg, String traceId) {
        super(message);
        this.errCode = errCode == null ? "" : errCode;
        this.errMsg = errMsg == null ? "" : errMsg;
        this.traceId = traceId == null ? "" : traceId;
    }

    public String getErrCode() {
        return errCode;
    }

    public String getErrMsg() {
        return errMsg;
    }

    public String getTraceId() {
        return traceId;
    }
}
