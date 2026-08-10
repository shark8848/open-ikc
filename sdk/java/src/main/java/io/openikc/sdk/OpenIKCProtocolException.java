package io.openikc.sdk;

/**
 * 响应不符合统一响应壳协议，或非 2xx 且无法解析统一壳（对齐 Python OpenIKCProtocolError / OpenIKCHTTPStatusError）。
 */
public class OpenIKCProtocolException extends OpenIKCTransportException {

    private final int statusCode;
    private final String body;

    public OpenIKCProtocolException(String message, String traceId) {
        this(message, 0, "", traceId);
    }

    public OpenIKCProtocolException(String message, int statusCode, String body, String traceId) {
        super(message, traceId);
        this.statusCode = statusCode;
        this.body = body == null ? "" : body;
    }

    public int getStatusCode() {
        return statusCode;
    }

    public String getBody() {
        return body;
    }
}
