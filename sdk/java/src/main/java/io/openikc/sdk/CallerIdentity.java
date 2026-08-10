package io.openikc.sdk;

import java.util.ArrayList;
import java.util.List;

/**
 * 调用方身份与 AUTHZ 上下文；仅非空字段透传为请求头（对齐 Python CallerIdentity）。
 */
public final class CallerIdentity {

    private final String userId;
    private final String tenantId;
    private final List<String> roles;
    private final List<String> permissions;
    private final List<String> denyPermissions;
    private final String authSystem;

    private CallerIdentity(Builder b) {
        this.userId = b.userId;
        this.tenantId = b.tenantId;
        this.roles = b.roles == null ? List.of() : List.copyOf(b.roles);
        this.permissions = b.permissions == null ? List.of() : List.copyOf(b.permissions);
        this.denyPermissions = b.denyPermissions == null ? List.of() : List.copyOf(b.denyPermissions);
        this.authSystem = b.authSystem;
    }

    public String getUserId() {
        return userId;
    }

    public String getTenantId() {
        return tenantId;
    }

    public List<String> getRoles() {
        return roles;
    }

    public List<String> getPermissions() {
        return permissions;
    }

    public List<String> getDenyPermissions() {
        return denyPermissions;
    }

    public String getAuthSystem() {
        return authSystem;
    }

    public static Builder builder() {
        return new Builder();
    }

    public static final class Builder {
        private String userId;
        private String tenantId;
        private List<String> roles;
        private List<String> permissions;
        private List<String> denyPermissions;
        private String authSystem;

        public Builder userId(String v) {
            this.userId = v;
            return this;
        }

        public Builder tenantId(String v) {
            this.tenantId = v;
            return this;
        }

        public Builder roles(List<String> v) {
            this.roles = v == null ? new ArrayList<>() : new ArrayList<>(v);
            return this;
        }

        public Builder permissions(List<String> v) {
            this.permissions = v == null ? new ArrayList<>() : new ArrayList<>(v);
            return this;
        }

        public Builder denyPermissions(List<String> v) {
            this.denyPermissions = v == null ? new ArrayList<>() : new ArrayList<>(v);
            return this;
        }

        public Builder authSystem(String v) {
            this.authSystem = v;
            return this;
        }

        public CallerIdentity build() {
            return new CallerIdentity(this);
        }
    }
}
