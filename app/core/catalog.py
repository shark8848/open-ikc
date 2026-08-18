API_CATALOG = [
    {
        "category": "知识库",
        "tag": "knowledge-base",
        "routes": [
            {
                "method": "POST",
                "path": "/api/v1/knowledge-bases/create",
                "summary": "创建知识库",
            },
            {
                "method": "POST",
                "path": "/api/v1/knowledge-bases/update",
                "summary": "修改知识库信息",
            },
            {
                "method": "POST",
                "path": "/api/v1/knowledge-bases/query",
                "summary": "查询知识库列表",
            },
            {
                "method": "GET",
                "path": "/api/v1/knowledge-bases/{kb_id}",
                "summary": "查询知识库详情",
            },
            {
                "method": "GET",
                "path": "/api/v1/knowledge-bases/{kb_id}/wiki/tree",
                "summary": "查询 Wiki 库页面树",
            },
            {
                "method": "GET",
                "path": "/api/v1/knowledge-bases/{kb_id}/wiki/page",
                "summary": "查询 Wiki 页面详情",
            },
            {
                "method": "GET",
                "path": "/api/v1/knowledge-bases/{kb_id}/wiki/search",
                "summary": "检索 Wiki 库页面",
            },
        ],
    },
    {
        "category": "文档",
        "tag": "document",
        "routes": [
            {
                "method": "POST",
                "path": "/api/v1/knowledge-documents/ingest",
                "summary": "接入知识源",
            },
            {
                "method": "POST",
                "path": "/api/v1/knowledge-documents/ingest-and-parse",
                "summary": "一体化接入并解析",
            },
            {
                "method": "GET",
                "path": "/api/v1/knowledge-documents/{doc_id}",
                "summary": "查询文档信息",
            },
            {
                "method": "POST",
                "path": "/api/v1/knowledge-documents/upload",
                "summary": "上传文档（7 天暂存）",
            },
            {
                "method": "GET",
                "path": "/api/v1/knowledge-documents/upload/{file_id}",
                "summary": "访问暂存文档",
            },
        ],
    },
    {
        "category": "解析",
        "tag": "parse",
        "routes": [
            {
                "method": "POST",
                "path": "/api/v1/knowledge-documents/parse",
                "summary": "启动文档解析",
            },
            {
                "method": "POST",
                "path": "/api/v1/knowledge-documents/parse-direct",
                "summary": "独立解析（免知识库）",
            },
            {
                "method": "GET",
                "path": "/api/v1/knowledge-documents/parse-result/query",
                "summary": "查询解析结果",
            },
            {
                "method": "GET",
                "path": "/api/v1/knowledge-documents/parse-result/issue-download-ticket",
                "summary": "获取解析结果下载凭证",
            },
            {
                "method": "GET",
                "path": "/api/v1/knowledge-documents/parse-result/download",
                "summary": "下载解析结果",
            },
        ],
    },
    {
        "category": "检索",
        "tag": "search",
        "routes": [
            {
                "method": "POST",
                "path": "/api/v1/knowledge-search/universal-search",
                "summary": "普通检索（证据列表）",
            },
            {
                "method": "POST",
                "path": "/api/v1/knowledge-search/deep-search",
                "summary": "深度检索（Agentic 多轮 + 带引用回答）",
            },
            {
                "method": "POST",
                "path": "/api/v1/knowledge-search/query",
                "summary": "普通检索兼容别名（指向 universal-search）",
            },
        ],
    },
]
