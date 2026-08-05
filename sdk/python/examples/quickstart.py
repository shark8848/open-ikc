#!/usr/bin/env python3
"""open-ikc-sdk 联调冒烟脚本：创建知识库 → 接入文档 → 解析 → 查询 → 下载 → 检索。

用法：
    export OPEN_PLATFORM_TOKEN=<token>
    python sdk/python/examples/quickstart.py [--base-url http://127.0.0.1:18000]
"""

from __future__ import annotations

import argparse
import os
import time

from open_ikc_sdk import CallerIdentity, OpenIKCClient
from open_ikc_sdk.errors import OpenIKCNotImplementedError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OpenIKC 开放平台 SDK 联调冒烟")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("OPEN_PLATFORM_BASE_URL", "http://127.0.0.1:18000"),
    )
    parser.add_argument("--token", default=os.environ.get("OPEN_PLATFORM_TOKEN", ""))
    parser.add_argument("--user-id", default="smoke_user")
    parser.add_argument("--tenant-id", default="smoke_tenant")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.token:
        print("未配置 OPEN_PLATFORM_TOKEN，跳过联调。")
        return 1

    suffix = str(int(time.time()))
    identity = CallerIdentity(user_id=args.user_id, tenant_id=args.tenant_id)

    with OpenIKCClient(base_url=args.base_url, token=args.token, identity=identity) as client:
        # 1. 创建知识库
        kb = client.knowledge_bases.create(kbName=f"SDK冒烟-{suffix}", kbDesc="SDK 联调冒烟")
        print(f"[1] 创建知识库 -> kbId={kb.kbId}")

        # 2. 接入文档
        ingest = client.documents.ingest(
            kbId=kb.kbId,
            source={"type": "file", "objectKey": f"oss://smoke/{suffix}/sample.pdf"},
            reqId=f"req_smoke_ingest_{suffix}",
            docTitle="冒烟样例文档",
        )
        doc_id = ingest.docId
        print(f"[2] 接入文档 -> ingestTaskId={ingest.ingestTaskId} docId={doc_id}")

        # 3. 启动解析（sync：请求内返回内联结果）
        task = client.parse.parse(
            kbId=kb.kbId,
            docId=doc_id,
            reqId=f"req_smoke_parse_{suffix}",
            executeMode="sync",
        )
        print(f"[3] 启动解析 -> taskId={task.taskId} status={task.taskStatus}")

        # 4. 查询解析结果
        result = client.parse.query_result(docId=doc_id)
        print(f"[4] 查询解析结果 -> parseStatus={result.parseStatus} pageCount={result.pageCount}")

        # 5. 签发下载凭证并下载
        ticket = client.parse.issue_download_ticket(docId=doc_id)
        print(f"[5] 签发下载凭证 -> ticket={ticket.ticket} expireAt={ticket.expireAt}")
        download = client.parse.download(docId=doc_id, ticket=ticket.ticket)
        print(f"[6] 下载解析结果 -> docId={download.docId} format={download.format}")

        # 7. 统一检索问答（平台占位期预期 501001）
        try:
            search = client.search.query(query="冒烟问题", kbId=kb.kbId)
            print(f"[7] 检索 -> answer={search.answer[:40]!r} results={len(search.results)}")
        except OpenIKCNotImplementedError as exc:
            print(f"[7] 检索（平台占位）-> {exc.err_code} {exc.err_msg}")

        # 8. 运行时契约自检
        catalog = client.fetch_catalog()
        print(f"[8] API 目录 -> {len(catalog)} 个分类")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
