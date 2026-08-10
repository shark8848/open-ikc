package io.openikc.sdk;

/**
 * OpenIKC SDK 异常层级（对齐 Python SDK errors.py）。
 *
 * <ul>
 *   <li>{@link OpenIKCError}：所有异常基类</li>
 *   <li>{@link OpenIKCTransportException}：传输层异常（连接/超时/协议/非预期状态）</li>
 *   <li>{@link OpenIKCApiException}：平台返回统一响应壳但 errCode != 000000</li>
 * </ul>
 */
public class OpenIKCError extends RuntimeException {

    public OpenIKCError(String message) {
        super(message);
    }

    public OpenIKCError(String message, Throwable cause) {
        super(message, cause);
    }
}
