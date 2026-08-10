package io.openikc.sdk;

/**
 * 传输层异常：连接、超时、协议不符合、非预期 HTTP 状态。
 */
public class OpenIKCTransportException extends OpenIKCError {

    private final String traceId;

    public OpenIKCTransportException(String message, String traceId) {
        super(message);
        this.traceId = traceId == null ? "" : traceId;
    }

    public OpenIKCTransportException(String message, Throwable cause, String traceId) {
        super(message, cause);
        this.traceId = traceId == null ? "" : traceId;
    }

    public String getTraceId() {
        return traceId;
    }
}
