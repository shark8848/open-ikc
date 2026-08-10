package io.openikc.sdk;

/**
 * 无法建立连接（对齐 Python OpenIKCConnectionError）。
 */
public class OpenIKCConnectionException extends OpenIKCTransportException {

    public OpenIKCConnectionException(String message, String traceId) {
        super(message, traceId);
    }

    public OpenIKCConnectionException(String message, Throwable cause, String traceId) {
        super(message, cause, traceId);
    }
}
