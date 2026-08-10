package io.openikc.sdk.model;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * 文档域模型（对齐 Python models/document.py）。
 */
public final class Documents {

    private Documents() {
    }

    /** 文档来源对象：url / file / directory / archive 四种形态。 */
    public static final class DocumentSource {
        private static final Set<String> SOURCE_FIELDS = Set.of(
                "type", "url", "objectKey", "fileToken", "archive", "directory", "metadata");

        private String type = "file";
        private String url = "";
        private String objectKey = "";
        private String fileToken = "";
        private Map<String, Object> archive = new LinkedHashMap<>();
        private Map<String, Object> directory = new LinkedHashMap<>();
        private Map<String, Object> metadata = new LinkedHashMap<>();
        private Map<String, Object> extra = new LinkedHashMap<>();

        public static DocumentSource fromDict(Map<String, Object> data) {
            DocumentSource s = new DocumentSource();
            s.type = Models.str(data, "type", "file");
            s.url = Models.str(data, "url");
            s.objectKey = Models.str(data, "objectKey");
            s.fileToken = Models.str(data, "fileToken");
            s.archive = Models.obj(data, "archive");
            s.directory = Models.obj(data, "directory");
            s.metadata = Models.obj(data, "metadata");
            s.extra = Models.extra(data, SOURCE_FIELDS);
            return s;
        }

        public String getType() {
            return type;
        }

        public String getUrl() {
            return url;
        }

        public String getObjectKey() {
            return objectKey;
        }

        public String getFileToken() {
            return fileToken;
        }

        public Map<String, Object> getArchive() {
            return archive;
        }

        public Map<String, Object> getDirectory() {
            return directory;
        }

        public Map<String, Object> getMetadata() {
            return metadata;
        }

        public Map<String, Object> getExtra() {
            return extra;
        }
    }

    /** 接入知识源结果。 */
    public static final class DocumentIngestResult {
        private static final Set<String> FIELDS = Set.of(
                "ingestTaskId", "docId", "docIds", "taskStatus", "sourceType", "sourceStats", "ingestTime");

        private final String ingestTaskId;
        private final String taskStatus;
        private final String sourceType;
        private final String ingestTime;
        private final String docId;
        private final List<String> docIds;
        private final Map<String, Object> sourceStats;
        private final Map<String, Object> extra;

        public DocumentIngestResult(String ingestTaskId, String taskStatus, String sourceType,
                                    String ingestTime, String docId, List<String> docIds,
                                    Map<String, Object> sourceStats, Map<String, Object> extra) {
            this.ingestTaskId = ingestTaskId;
            this.taskStatus = taskStatus;
            this.sourceType = sourceType;
            this.ingestTime = ingestTime;
            this.docId = docId;
            this.docIds = docIds == null ? new ArrayList<>() : docIds;
            this.sourceStats = sourceStats == null ? new LinkedHashMap<>() : sourceStats;
            this.extra = extra == null ? new LinkedHashMap<>() : extra;
        }

        public static DocumentIngestResult fromDict(Map<String, Object> data) {
            Object docId = data.get("docId");
            return new DocumentIngestResult(
                    Models.str(data, "ingestTaskId"),
                    Models.str(data, "taskStatus"),
                    Models.str(data, "sourceType"),
                    Models.str(data, "ingestTime"),
                    docId == null ? null : String.valueOf(docId),
                    Models.strList(data, "docIds"),
                    Models.obj(data, "sourceStats"),
                    Models.extra(data, FIELDS));
        }

        public String getIngestTaskId() {
            return ingestTaskId;
        }

        public String getTaskStatus() {
            return taskStatus;
        }

        public String getSourceType() {
            return sourceType;
        }

        public String getIngestTime() {
            return ingestTime;
        }

        public String getDocId() {
            return docId;
        }

        public List<String> getDocIds() {
            return docIds;
        }

        public Map<String, Object> getSourceStats() {
            return sourceStats;
        }

        public Map<String, Object> getExtra() {
            return extra;
        }
    }

    /** 一体化接入并解析结果。 */
    public static final class DocumentIngestAndParseResult {
        private static final Set<String> FIELDS = Set.of(
                "ingestTaskId", "parseTaskId", "docId", "taskStatus", "executeMode", "resultInline");

        private final String ingestTaskId;
        private final String parseTaskId;
        private final String taskStatus;
        private final String executeMode;
        private final String docId;
        private final Map<String, Object> resultInline;
        private final Map<String, Object> extra;

        public DocumentIngestAndParseResult(String ingestTaskId, String parseTaskId, String taskStatus,
                                            String executeMode, String docId, Map<String, Object> resultInline,
                                            Map<String, Object> extra) {
            this.ingestTaskId = ingestTaskId;
            this.parseTaskId = parseTaskId;
            this.taskStatus = taskStatus;
            this.executeMode = executeMode;
            this.docId = docId;
            this.resultInline = resultInline == null ? new LinkedHashMap<>() : resultInline;
            this.extra = extra == null ? new LinkedHashMap<>() : extra;
        }

        public static DocumentIngestAndParseResult fromDict(Map<String, Object> data) {
            Object docId = data.get("docId");
            return new DocumentIngestAndParseResult(
                    Models.str(data, "ingestTaskId"),
                    Models.str(data, "parseTaskId"),
                    Models.str(data, "taskStatus"),
                    Models.str(data, "executeMode"),
                    docId == null ? null : String.valueOf(docId),
                    Models.obj(data, "resultInline"),
                    Models.extra(data, FIELDS));
        }

        public String getIngestTaskId() {
            return ingestTaskId;
        }

        public String getParseTaskId() {
            return parseTaskId;
        }

        public String getTaskStatus() {
            return taskStatus;
        }

        public String getExecuteMode() {
            return executeMode;
        }

        public String getDocId() {
            return docId;
        }

        public Map<String, Object> getResultInline() {
            return resultInline;
        }

        public Map<String, Object> getExtra() {
            return extra;
        }
    }

    /** 文档信息。 */
    public static final class DocumentInfo {
        private static final Set<String> FIELDS = Set.of(
                "docId", "docTitle", "kbId", "sourceType", "sourceUrl", "objectKey",
                "tags", "metadata", "status", "ingestTime", "updateTime");

        private final String docId;
        private final String docTitle;
        private final String kbId;
        private final String sourceType;
        private final String sourceUrl;
        private final String objectKey;
        private final List<String> tags;
        private final Map<String, Object> metadata;
        private final String status;
        private final String ingestTime;
        private final String updateTime;
        private final Map<String, Object> extra;

        public DocumentInfo(String docId, String docTitle, String kbId, String sourceType, String sourceUrl,
                            String objectKey, List<String> tags, Map<String, Object> metadata, String status,
                            String ingestTime, String updateTime, Map<String, Object> extra) {
            this.docId = docId;
            this.docTitle = docTitle;
            this.kbId = kbId;
            this.sourceType = sourceType;
            this.sourceUrl = sourceUrl;
            this.objectKey = objectKey;
            this.tags = tags == null ? new ArrayList<>() : tags;
            this.metadata = metadata == null ? new LinkedHashMap<>() : metadata;
            this.status = status;
            this.ingestTime = ingestTime;
            this.updateTime = updateTime;
            this.extra = extra == null ? new LinkedHashMap<>() : extra;
        }

        public static DocumentInfo fromDict(Map<String, Object> data) {
            Object updateTime = data.get("updateTime");
            return new DocumentInfo(
                    Models.str(data, "docId"),
                    Models.str(data, "docTitle"),
                    Models.str(data, "kbId"),
                    Models.str(data, "sourceType"),
                    Models.str(data, "sourceUrl"),
                    Models.str(data, "objectKey"),
                    Models.strList(data, "tags"),
                    Models.obj(data, "metadata"),
                    Models.str(data, "status"),
                    Models.str(data, "ingestTime"),
                    updateTime == null ? null : String.valueOf(updateTime),
                    Models.extra(data, FIELDS));
        }

        public String getDocId() {
            return docId;
        }

        public String getDocTitle() {
            return docTitle;
        }

        public String getKbId() {
            return kbId;
        }

        public String getSourceType() {
            return sourceType;
        }

        public String getSourceUrl() {
            return sourceUrl;
        }

        public String getObjectKey() {
            return objectKey;
        }

        public List<String> getTags() {
            return tags;
        }

        public Map<String, Object> getMetadata() {
            return metadata;
        }

        public String getStatus() {
            return status;
        }

        public String getIngestTime() {
            return ingestTime;
        }

        public String getUpdateTime() {
            return updateTime;
        }

        public Map<String, Object> getExtra() {
            return extra;
        }
    }
}
