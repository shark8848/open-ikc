package io.openikc.sdk;

/**
 * 请求超时（对齐 Python OpenIKCTimeoutError）。
 */
public class OpenIKCTimeoutException extends OpenIKCTransportException {

    public OpenIKCTimeoutException(String message, String traceId) {
        super(message, traceId);
    }

    public OpenIKCTimeoutException(String message, Throwable cause, String traceId) {
        super(message, cause, traceId);
    }
}
