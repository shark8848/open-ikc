package io.openikc.sdk.model;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * 检索域模型（对齐 Python models/search.py）。
 */
public final class Search {

    private Search() {
    }

    /** 检索结果条目。 */
    public static final class SearchResultItem {
        private static final Set<String> FIELDS = Set.of("docId", "score", "snippet", "citation");

        private final String docId;
        private final Double score;
        private final String snippet;
        private final Map<String, Object> citation;
        private final Map<String, Object> extra;

        public SearchResultItem(String docId, Double score, String snippet,
                                Map<String, Object> citation, Map<String, Object> extra) {
            this.docId = docId;
            this.score = score;
            this.snippet = snippet;
            this.citation = citation == null ? new LinkedHashMap<>() : citation;
            this.extra = extra == null ? new LinkedHashMap<>() : extra;
        }

        public static SearchResultItem fromDict(Map<String, Object> data) {
            Object score = data.get("score");
            Double scoreVal = null;
            if (score instanceof Number n) {
                scoreVal = n.doubleValue();
            } else if (score != null) {
                try {
                    scoreVal = Double.parseDouble(String.valueOf(score));
                } catch (NumberFormatException ignored) {
                    scoreVal = null;
                }
            }
            return new SearchResultItem(
                    Models.str(data, "docId"),
                    scoreVal,
                    Models.str(data, "snippet"),
                    Models.obj(data, "citation"),
                    Models.extra(data, FIELDS));
        }

        public String getDocId() {
            return docId;
        }

        public Double getScore() {
            return score;
        }

        public String getSnippet() {
            return snippet;
        }

        public Map<String, Object> getCitation() {
            return citation;
        }

        public Map<String, Object> getExtra() {
            return extra;
        }
    }

    /** 统一检索问答结果。 */
    public static final class SearchResult {
        private static final Set<String> FIELDS = Set.of("answer", "results");

        private final String answer;
        private final List<SearchResultItem> results;
        private final Map<String, Object> extra;

        public SearchResult(String answer, List<SearchResultItem> results, Map<String, Object> extra) {
            this.answer = answer == null ? "" : answer;
            this.results = results == null ? new ArrayList<>() : results;
            this.extra = extra == null ? new LinkedHashMap<>() : extra;
        }

        public static SearchResult fromDict(Map<String, Object> data) {
            List<SearchResultItem> items = new ArrayList<>();
            Object raw = data.get("results");
            if (raw instanceof List<?> list) {
                for (Object item : list) {
                    if (item instanceof Map) {
                        items.add(SearchResultItem.fromDict((Map<String, Object>) item));
                    }
                }
            }
            return new SearchResult(
                    Models.str(data, "answer"),
                    items,
                    Models.extra(data, FIELDS));
        }

        public String getAnswer() {
            return answer;
        }

        public List<SearchResultItem> getResults() {
            return results;
        }

        public Map<String, Object> getExtra() {
            return extra;
        }
    }
}
