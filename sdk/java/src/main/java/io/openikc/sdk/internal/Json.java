package io.openikc.sdk.internal;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 极简 JSON 解析器（JDK 无内置 JSON API；本 SDK 保持零第三方依赖）。
 *
 * <p>支持解析统一响应壳所需的结构：对象、数组、字符串、数字、布尔、null。
 * 字符串含转义（引号、反斜杠、斜杠、b、f、n、r、t、uXXXX）。数字解析为 Long 或 Double。
 */
public final class Json {

    private Json() {
    }

    public static Object parse(String text) {
        Parser p = new Parser(text);
        Object value = p.parseValue();
        p.skipWhitespace();
        if (!p.atEnd()) {
            throw new IllegalArgumentException("JSON 末尾存在多余字符: 位置 " + p.pos);
        }
        return value;
    }

    @SuppressWarnings("unchecked")
    public static Map<String, Object> parseObject(String text) {
        Object value = parse(text);
        if (!(value instanceof Map)) {
            throw new IllegalArgumentException("JSON 顶层不是对象");
        }
        return (Map<String, Object>) value;
    }

    public static String quote(String s) {
        StringBuilder sb = new StringBuilder(s.length() + 2);
        sb.append('"');
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"':
                    sb.append("\\\"");
                    break;
                case '\\':
                    sb.append("\\\\");
                    break;
                case '\n':
                    sb.append("\\n");
                    break;
                case '\r':
                    sb.append("\\r");
                    break;
                case '\t':
                    sb.append("\\t");
                    break;
                case '\b':
                    sb.append("\\b");
                    break;
                case '\f':
                    sb.append("\\f");
                    break;
                default:
                    if (c < 0x20) {
                        sb.append(String.format("\\u%04x", (int) c));
                    } else {
                        sb.append(c);
                    }
            }
        }
        sb.append('"');
        return sb.toString();
    }

    /** 安全取值：Map 中按 key 取值，缺省返回 defaultValue。 */
    public static <T> T get(Map<String, Object> map, String key, T defaultValue) {
        Object v = map.get(key);
        if (v == null) {
            return defaultValue;
        }
        @SuppressWarnings("unchecked")
        T casted = (T) v;
        return casted;
    }

    private static final class Parser {
        private final String s;
        private int pos;

        Parser(String s) {
            this.s = s;
        }

        boolean atEnd() {
            return pos >= s.length();
        }

        void skipWhitespace() {
            while (pos < s.length()) {
                char c = s.charAt(pos);
                if (c == ' ' || c == '\t' || c == '\n' || c == '\r') {
                    pos++;
                } else {
                    break;
                }
            }
        }

        char peek() {
            if (atEnd()) {
                throw new IllegalArgumentException("JSON 意外结束");
            }
            return s.charAt(pos);
        }

        char next() {
            char c = peek();
            pos++;
            return c;
        }

        void expect(char expected) {
            char c = next();
            if (c != expected) {
                throw new IllegalArgumentException("JSON 期望 '" + expected + "'，实际 '" + c + "'（位置 " + (pos - 1) + "）");
            }
        }

        Object parseValue() {
            skipWhitespace();
            char c = peek();
            switch (c) {
                case '{':
                    return parseObjectValue();
                case '[':
                    return parseArray();
                case '"':
                    return parseString();
                case 't':
                    expectLiteral("true");
                    return Boolean.TRUE;
                case 'f':
                    expectLiteral("false");
                    return Boolean.FALSE;
                case 'n':
                    expectLiteral("null");
                    return null;
                default:
                    if (c == '-' || (c >= '0' && c <= '9')) {
                        return parseNumber();
                    }
                    throw new IllegalArgumentException("JSON 无法识别的字符 '" + c + "'（位置 " + pos + "）");
            }
        }

        void expectLiteral(String lit) {
            for (int i = 0; i < lit.length(); i++) {
                expect(lit.charAt(i));
            }
        }

        Map<String, Object> parseObjectValue() {
            Map<String, Object> map = new LinkedHashMap<>();
            expect('{');
            skipWhitespace();
            if (peek() == '}') {
                pos++;
                return map;
            }
            while (true) {
                skipWhitespace();
                String key = parseString();
                skipWhitespace();
                expect(':');
                Object value = parseValue();
                map.put(key, value);
                skipWhitespace();
                char c = next();
                if (c == ',') {
                    continue;
                }
                if (c == '}') {
                    break;
                }
                throw new IllegalArgumentException("JSON 对象期望 ',' 或 '}'（位置 " + (pos - 1) + "）");
            }
            return map;
        }

        List<Object> parseArray() {
            List<Object> list = new ArrayList<>();
            expect('[');
            skipWhitespace();
            if (peek() == ']') {
                pos++;
                return list;
            }
            while (true) {
                Object value = parseValue();
                list.add(value);
                skipWhitespace();
                char c = next();
                if (c == ',') {
                    continue;
                }
                if (c == ']') {
                    break;
                }
                throw new IllegalArgumentException("JSON 数组期望 ',' 或 ']'（位置 " + (pos - 1) + "）");
            }
            return list;
        }

        String parseString() {
            expect('"');
            StringBuilder sb = new StringBuilder();
            while (true) {
                if (atEnd()) {
                    throw new IllegalArgumentException("JSON 字符串未闭合");
                }
                char c = next();
                if (c == '"') {
                    break;
                }
                if (c == '\\') {
                    char e = next();
                    switch (e) {
                        case '"':
                            sb.append('"');
                            break;
                        case '\\':
                            sb.append('\\');
                            break;
                        case '/':
                            sb.append('/');
                            break;
                        case 'b':
                            sb.append('\b');
                            break;
                        case 'f':
                            sb.append('\f');
                            break;
                        case 'n':
                            sb.append('\n');
                            break;
                        case 'r':
                            sb.append('\r');
                            break;
                        case 't':
                            sb.append('\t');
                            break;
                        case 'u':
                            if (pos + 4 > s.length()) {
                                throw new IllegalArgumentException("JSON \\u 转义不完整");
                            }
                            String hex = s.substring(pos, pos + 4);
                            sb.append((char) Integer.parseInt(hex, 16));
                            pos += 4;
                            break;
                        default:
                            throw new IllegalArgumentException("JSON 非法转义 '\\" + e + "'");
                    }
                } else {
                    sb.append(c);
                }
            }
            return sb.toString();
        }

        Object parseNumber() {
            int start = pos;
            if (peek() == '-') {
                pos++;
            }
            while (!atEnd() && Character.isDigit(peek())) {
                pos++;
            }
            boolean isFloat = false;
            if (!atEnd() && peek() == '.') {
                isFloat = true;
                pos++;
                while (!atEnd() && Character.isDigit(peek())) {
                    pos++;
                }
            }
            if (!atEnd() && (peek() == 'e' || peek() == 'E')) {
                isFloat = true;
                pos++;
                if (!atEnd() && (peek() == '+' || peek() == '-')) {
                    pos++;
                }
                while (!atEnd() && Character.isDigit(peek())) {
                    pos++;
                }
            }
            String num = s.substring(start, pos);
            if (isFloat) {
                return Double.parseDouble(num);
            }
            try {
                return Long.parseLong(num);
            } catch (NumberFormatException e) {
                return Double.parseDouble(num);
            }
        }
    }
}
