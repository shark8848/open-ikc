package io.openikc.sdk;

/**
 * 按错误码映射的具体业务异常子类。
 */
public final class ApiExceptions {

    private ApiExceptions() {
    }

    /** 参数校验失败（100001）。 */
    public static final class ValidationException extends OpenIKCApiException {
        public ValidationException(String message, String errCode, String errMsg, String traceId) {
            super(message, errCode, errMsg, traceId);
        }
    }

    /** 未认证或认证失败（100401）。 */
    public static final class UnauthorizedException extends OpenIKCApiException {
        public UnauthorizedException(String message, String errCode, String errMsg, String traceId) {
            super(message, errCode, errMsg, traceId);
        }
    }

    /** 无权限访问（100403）。 */
    public static final class ForbiddenException extends OpenIKCApiException {
        public ForbiddenException(String message, String errCode, String errMsg, String traceId) {
            super(message, errCode, errMsg, traceId);
        }
    }

    /** 资源不存在（100404）。 */
    public static final class NotFoundException extends OpenIKCApiException {
        public NotFoundException(String message, String errCode, String errMsg, String traceId) {
            super(message, errCode, errMsg, traceId);
        }
    }

    /** 请求方法不允许（100405）。 */
    public static final class MethodNotAllowedException extends OpenIKCApiException {
        public MethodNotAllowedException(String message, String errCode, String errMsg, String traceId) {
            super(message, errCode, errMsg, traceId);
        }
    }

    /** 资源冲突（100409）。 */
    public static final class ConflictException extends OpenIKCApiException {
        public ConflictException(String message, String errCode, String errMsg, String traceId) {
            super(message, errCode, errMsg, traceId);
        }
    }

    /** 平台接口占位未实现（501001）。 */
    public static final class NotImplementedException extends OpenIKCApiException {
        public NotImplementedException(String message, String errCode, String errMsg, String traceId) {
            super(message, errCode, errMsg, traceId);
        }
    }

    /** 平台系统内部错误（999999）。 */
    public static final class SystemException extends OpenIKCApiException {
        public SystemException(String message, String errCode, String errMsg, String traceId) {
            super(message, errCode, errMsg, traceId);
        }
    }

    /** 2xxxxx 业务错误或未知错误码。 */
    public static final class BusinessException extends OpenIKCApiException {
        public BusinessException(String message, String errCode, String errMsg, String traceId) {
            super(message, errCode, errMsg, traceId);
        }
    }

    /** 按错误码生成对应异常；未知错误码映射为 BusinessException。 */
    public static OpenIKCApiException fromCode(String errCode, String errMsg, String traceId) {
        String message = (errCode + " " + errMsg).trim();
        switch (errCode) {
            case "100001":
                return new ValidationException(message, errCode, errMsg, traceId);
            case "100401":
                return new UnauthorizedException(message, errCode, errMsg, traceId);
            case "100403":
                return new ForbiddenException(message, errCode, errMsg, traceId);
            case "100404":
                return new NotFoundException(message, errCode, errMsg, traceId);
            case "100405":
                return new MethodNotAllowedException(message, errCode, errMsg, traceId);
            case "100409":
                return new ConflictException(message, errCode, errMsg, traceId);
            case "501001":
                return new NotImplementedException(message, errCode, errMsg, traceId);
            case "999999":
                return new SystemException(message, errCode, errMsg, traceId);
            default:
                return new BusinessException(message, errCode, errMsg, traceId);
        }
    }
}
