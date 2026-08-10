package io.openikc.sdk.model;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;

/**
 * 解析域模型（对齐 Python models/parse.py）。
 */
public final class Parse {

    private Parse() {
    }

    /** 解析任务。 */
    public static final class ParseTask {
        private static final Set<String> FIELDS = Set.of("taskId", "taskStatus", "executeMode", "resultInline");

        private final String taskId;
        private final String taskStatus;
        private final String executeMode;
        private final Map<String, Object> resultInline;
        private final Map<String, Object> extra;

        public ParseTask(String taskId, String taskStatus, String executeMode,
                         Map<String, Object> resultInline, Map<String, Object> extra) {
            this.taskId = taskId;
            this.taskStatus = taskStatus;
            this.executeMode = executeMode;
            this.resultInline = resultInline == null ? new LinkedHashMap<>() : resultInline;
            this.extra = extra == null ? new LinkedHashMap<>() : extra;
        }

        public static ParseTask fromDict(Map<String, Object> data) {
            return new ParseTask(
                    Models.str(data, "taskId"),
                    Models.str(data, "taskStatus"),
                    Models.str(data, "executeMode"),
                    Models.obj(data, "resultInline"),
                    Models.extra(data, FIELDS));
        }

        public String getTaskId() {
            return taskId;
        }

        public String getTaskStatus() {
            return taskStatus;
        }

        public String getExecuteMode() {
            return executeMode;
        }

        public Map<String, Object> getResultInline() {
            return resultInline;
        }

        public Map<String, Object> getExtra() {
            return extra;
        }
    }

    /** 解析结果摘要。 */
    public static final class ParseResult {
        private static final Set<String> FIELDS = Set.of("parseStatus", "resultFormat", "pageCount", "chunkCount", "failedReason");

        private final String parseStatus;
        private final Map<String, Object> resultFormat;
        private final int pageCount;
        private final int chunkCount;
        private final String failedReason;
        private final Map<String, Object> extra;

        public ParseResult(String parseStatus, Map<String, Object> resultFormat, int pageCount,
                           int chunkCount, String failedReason, Map<String, Object> extra) {
            this.parseStatus = parseStatus;
            this.resultFormat = resultFormat == null ? new LinkedHashMap<>() : resultFormat;
            this.pageCount = pageCount;
            this.chunkCount = chunkCount;
            this.failedReason = failedReason;
            this.extra = extra == null ? new LinkedHashMap<>() : extra;
        }

        public static ParseResult fromDict(Map<String, Object> data) {
            return new ParseResult(
                    Models.str(data, "parseStatus"),
                    Models.obj(data, "resultFormat"),
                    Models.integer(data, "pageCount", 0),
                    Models.integer(data, "chunkCount", 0),
                    Models.str(data, "failedReason"),
                    Models.extra(data, FIELDS));
        }

        public String getParseStatus() {
            return parseStatus;
        }

        public Map<String, Object> getResultFormat() {
            return resultFormat;
        }

        public int getPageCount() {
            return pageCount;
        }

        public int getChunkCount() {
            return chunkCount;
        }

        public String getFailedReason() {
            return failedReason;
        }

        public Map<String, Object> getExtra() {
            return extra;
        }
    }

    /** 解析结果下载凭证。 */
    public static final class DownloadTicket {
        private static final Set<String> FIELDS = Set.of("ticket", "expireAt", "downloadPath");

        private final String ticket;
        private final String expireAt;
        private final String downloadPath;
        private final Map<String, Object> extra;

        public DownloadTicket(String ticket, String expireAt, String downloadPath, Map<String, Object> extra) {
            this.ticket = ticket;
            this.expireAt = expireAt;
            this.downloadPath = downloadPath;
            this.extra = extra == null ? new LinkedHashMap<>() : extra;
        }

        public static DownloadTicket fromDict(Map<String, Object> data) {
            return new DownloadTicket(
                    Models.str(data, "ticket"),
                    Models.str(data, "expireAt"),
                    Models.str(data, "downloadPath"),
                    Models.extra(data, FIELDS));
        }

        public String getTicket() {
            return ticket;
        }

        public String getExpireAt() {
            return expireAt;
        }

        public String getDownloadPath() {
            return downloadPath;
        }

        public Map<String, Object> getExtra() {
            return extra;
        }
    }

    /** 下载结果信息（文件流落地前为统一体元数据）。 */
    public static final class DownloadResult {
        private static final Set<String> FIELDS = Set.of("docId", "taskId", "downloadPath", "format", "note");

        private final String docId;
        private final String taskId;
        private final String downloadPath;
        private final String format;
        private final String note;
        private final Map<String, Object> extra;

        public DownloadResult(String docId, String taskId, String downloadPath, String format,
                              String note, Map<String, Object> extra) {
            this.docId = docId;
            this.taskId = taskId;
            this.downloadPath = downloadPath;
            this.format = format;
            this.note = note;
            this.extra = extra == null ? new LinkedHashMap<>() : extra;
        }

        public static DownloadResult fromDict(Map<String, Object> data) {
            return new DownloadResult(
                    Models.str(data, "docId"),
                    Models.str(data, "taskId"),
                    Models.str(data, "downloadPath"),
                    Models.str(data, "format", "json"),
                    Models.str(data, "note"),
                    Models.extra(data, FIELDS));
        }

        public String getDocId() {
            return docId;
        }

        public String getTaskId() {
            return taskId;
        }

        public String getDownloadPath() {
            return downloadPath;
        }

        public String getFormat() {
            return format;
        }

        public String getNote() {
            return note;
        }

        public Map<String, Object> getExtra() {
            return extra;
        }
    }
}
