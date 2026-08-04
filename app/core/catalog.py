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
                "path": "/api/v1/knowledge-search/query",
                "summary": "统一检索问答",
            },
        ],
    },
]
