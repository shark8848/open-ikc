package io.openikc.sdk.examples;

import io.openikc.sdk.OpenIKCApiException;
import io.openikc.sdk.OpenIKCClient;
import io.openikc.sdk.OpenIKCError;
import io.openikc.sdk.model.KnowledgeBase;

import java.util.List;
import java.util.Map;

/**
 * 真实平台冒烟：连接本机 18000 平台，验证 catalog / KB 查询全链路。
 * 用法：mvn -q compile exec:java -Dexec.mainClass=io.openikc.sdk.examples.Smoke -Dexec.args="http://127.0.0.1:18000 <token>"
 */
public final class Smoke {

    public static void main(String[] args) {
        String baseUrl = args.length > 0 ? args[0] : "http://127.0.0.1:18000";
        String token = args.length > 1 ? args[1] : "";

        try (OpenIKCClient client = new OpenIKCClient.Builder(baseUrl).token(token).build()) {
            System.out.println("[1/3] fetchCatalog ->");
            List<Map<String, Object>> catalog = client.fetchCatalog();
            System.out.println("      categories=" + catalog.size());

            System.out.println("[2/3] fetchErrorCodes ->");
            List<Map<String, Object>> codes = client.fetchErrorCodes();
            System.out.println("      codes=" + codes.size());

            System.out.println("[3/3] knowledgeBases().query ->");
            KnowledgeBase.KnowledgeBasePage page = client.knowledgeBases().query(1, 10, null, null, null, null, null);
            System.out.println("      total=" + page.getTotal() + " items=" + page.getItems().size());
            if (!page.getItems().isEmpty()) {
                KnowledgeBase kb = page.getItems().get(0);
                System.out.println("      first kbId=" + kb.getKbId() + " name=" + kb.getKbName());
            }
            System.out.println("SMOKE OK");
        } catch (OpenIKCApiException e) {
            System.err.println("业务异常: " + e.getErrCode() + " " + e.getErrMsg());
            System.exit(1);
        } catch (OpenIKCError e) {
            System.err.println("SDK 异常: " + e.getMessage());
            System.exit(1);
        }
    }
}
