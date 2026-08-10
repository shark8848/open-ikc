package io.openikc.sdk.model;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * 知识库信息（对齐 Python KnowledgeBase / KnowledgeBasePage / KnowledgeMetadataField）。
 */
public final class KnowledgeBase {

    private static final Set<String> KNOWLEDGE_BASE_FIELDS = Set.of(
            "kbId", "kbName", "kbType", "teamId", "orgId", "kbDesc", "bizDomain",
            "visibility", "metadataSchema", "createTime", "updateTime");

    private final String kbId;
    private final String kbName;
    private final String kbType;
    private final String teamId;
    private final String orgId;
    private final String kbDesc;
    private final String bizDomain;
    private final String visibility;
    private final List<KnowledgeMetadataField> metadataSchema;
    private final String createTime;
    private final String updateTime;
    private final Map<String, Object> extra;

    public KnowledgeBase(String kbId, String kbName, String kbType, String teamId, String orgId,
                         String kbDesc, String bizDomain, String visibility,
                         List<KnowledgeMetadataField> metadataSchema, String createTime,
                         String updateTime, Map<String, Object> extra) {
        this.kbId = kbId;
        this.kbName = kbName;
        this.kbType = kbType;
        this.teamId = teamId;
        this.orgId = orgId;
        this.kbDesc = kbDesc;
        this.bizDomain = bizDomain;
        this.visibility = visibility;
        this.metadataSchema = metadataSchema == null ? new ArrayList<>() : metadataSchema;
        this.createTime = createTime;
        this.updateTime = updateTime;
        this.extra = extra == null ? new LinkedHashMap<>() : extra;
    }

    public static KnowledgeBase fromDict(Map<String, Object> data) {
        List<KnowledgeMetadataField> schema = new ArrayList<>();
        Object raw = data.get("metadataSchema");
        if (raw instanceof List<?> list) {
            for (Object item : list) {
                if (item instanceof Map) {
                    schema.add(KnowledgeMetadataField.fromDict((Map<String, Object>) item));
                }
            }
        }
        return new KnowledgeBase(
                Models.str(data, "kbId"),
                Models.str(data, "kbName"),
                Models.str(data, "kbType", "personal"),
                Models.str(data, "teamId"),
                Models.str(data, "orgId"),
                Models.str(data, "kbDesc"),
                Models.str(data, "bizDomain", "general"),
                Models.str(data, "visibility", "private"),
                schema,
                data.get("createTime") == null ? null : String.valueOf(data.get("createTime")),
                data.get("updateTime") == null ? null : String.valueOf(data.get("updateTime")),
                Models.extra(data, KNOWLEDGE_BASE_FIELDS));
    }

    public String getKbId() {
        return kbId;
    }

    public String getKbName() {
        return kbName;
    }

    public String getKbType() {
        return kbType;
    }

    public String getTeamId() {
        return teamId;
    }

    public String getOrgId() {
        return orgId;
    }

    public String getKbDesc() {
        return kbDesc;
    }

    public String getBizDomain() {
        return bizDomain;
    }

    public String getVisibility() {
        return visibility;
    }

    public List<KnowledgeMetadataField> getMetadataSchema() {
        return metadataSchema;
    }

    public String getCreateTime() {
        return createTime;
    }

    public String getUpdateTime() {
        return updateTime;
    }

    public Map<String, Object> getExtra() {
        return extra;
    }

    /** 元数据字段定义（对应平台 metadataSchema[]）。 */
    public static final class KnowledgeMetadataField {
        private final String name;
        private final String type;
        private final boolean required;
        private final String description;
        private final Object defaultValue;
        private final List<String> enumValues;
        private final String pattern;
        private final Integer minLength;
        private final Integer maxLength;
        private final Object example;

        public KnowledgeMetadataField(String name, String type, boolean required, String description,
                                      Object defaultValue, List<String> enumValues, String pattern,
                                      Integer minLength, Integer maxLength, Object example) {
            this.name = name;
            this.type = type;
            this.required = required;
            this.description = description;
            this.defaultValue = defaultValue;
            this.enumValues = enumValues == null ? new ArrayList<>() : enumValues;
            this.pattern = pattern;
            this.minLength = minLength;
            this.maxLength = maxLength;
            this.example = example;
        }

        public static KnowledgeMetadataField fromDict(Map<String, Object> data) {
            Object minLen = data.get("minLength");
            Object maxLen = data.get("maxLength");
            return new KnowledgeMetadataField(
                    Models.str(data, "name"),
                    Models.str(data, "type"),
                    Boolean.TRUE.equals(data.get("required")),
                    Models.str(data, "description"),
                    data.get("defaultValue"),
                    Models.strList(data, "enum"),
                    Models.str(data, "pattern"),
                    minLen instanceof Number n ? n.intValue() : null,
                    maxLen instanceof Number n ? n.intValue() : null,
                    data.get("example"));
        }

        public String getName() {
            return name;
        }

        public String getType() {
            return type;
        }

        public boolean isRequired() {
            return required;
        }

        public String getDescription() {
            return description;
        }

        public Object getDefaultValue() {
            return defaultValue;
        }

        public List<String> getEnumValues() {
            return enumValues;
        }

        public String getPattern() {
            return pattern;
        }

        public Integer getMinLength() {
            return minLength;
        }

        public Integer getMaxLength() {
            return maxLength;
        }

        public Object getExample() {
            return example;
        }
    }

    /** 知识库分页查询结果。 */
    public static final class KnowledgeBasePage {
        private final int total;
        private final int page;
        private final int pageSize;
        private final List<KnowledgeBase> items;

        public KnowledgeBasePage(int total, int page, int pageSize, List<KnowledgeBase> items) {
            this.total = total;
            this.page = page;
            this.pageSize = pageSize;
            this.items = items == null ? new ArrayList<>() : items;
        }

        public static KnowledgeBasePage fromDict(Map<String, Object> data) {
            List<KnowledgeBase> items = new ArrayList<>();
            Object raw = data.get("items");
            if (raw instanceof List<?> list) {
                for (Object item : list) {
                    if (item instanceof Map) {
                        items.add(KnowledgeBase.fromDict((Map<String, Object>) item));
                    }
                }
            }
            return new KnowledgeBasePage(
                    Models.integer(data, "total", 0),
                    Models.integer(data, "page", 1),
                    Models.integer(data, "pageSize", 20),
                    items);
        }

        public int getTotal() {
            return total;
        }

        public int getPage() {
            return page;
        }

        public int getPageSize() {
            return pageSize;
        }

        public List<KnowledgeBase> getItems() {
            return items;
        }
    }
}
