package io.openikc.sdk.model;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * model 包辅助工具：安全取值与 extra 提取（对齐 Python model 的 from_dict 语义）。
 */
public final class Models {

    private Models() {
    }

    public static String str(Map<String, Object> data, String key, String def) {
        Object v = data.get(key);
        return v == null ? def : String.valueOf(v);
    }

    public static String str(Map<String, Object> data, String key) {
        return str(data, key, "");
    }

    public static int integer(Map<String, Object> data, String key, int def) {
        Object v = data.get(key);
        if (v == null) {
            return def;
        }
        if (v instanceof Number n) {
            return n.intValue();
        }
        try {
            return Integer.parseInt(String.valueOf(v));
        } catch (NumberFormatException e) {
            return def;
        }
    }

    public static double number(Map<String, Object> data, String key, double def) {
        Object v = data.get(key);
        if (v == null) {
            return def;
        }
        if (v instanceof Number n) {
            return n.doubleValue();
        }
        try {
            return Double.parseDouble(String.valueOf(v));
        } catch (NumberFormatException e) {
            return def;
        }
    }

    /** 取字符串列表；null 时返回空列表。 */
    public static List<String> strList(Map<String, Object> data, String key) {
        Object v = data.get(key);
        List<String> out = new ArrayList<>();
        if (v instanceof List<?> list) {
            for (Object item : list) {
                if (item != null) {
                    out.add(String.valueOf(item));
                }
            }
        }
        return out;
    }

    /** 取对象；null 或非 Map 时返回空 Map。 */
    @SuppressWarnings("unchecked")
    public static Map<String, Object> obj(Map<String, Object> data, String key) {
        Object v = data.get(key);
        if (v instanceof Map) {
            return (Map<String, Object>) v;
        }
        return new LinkedHashMap<>();
    }

    /** 提取 extra 字段：排除已知字段后剩余全部保留。 */
    public static Map<String, Object> extra(Map<String, Object> data, java.util.Set<String> knownFields) {
        Map<String, Object> out = new LinkedHashMap<>();
        for (Map.Entry<String, Object> e : data.entrySet()) {
            if (!knownFields.contains(e.getKey())) {
                out.put(e.getKey(), e.getValue());
            }
        }
        return out;
    }
}
