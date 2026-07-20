# 数据库设计文档

> 技术栈：PostgreSQL 17 + pgvector + SQLAlchemy 2.0（异步，asyncpg）
> 数据库名：`rag_kb`（默认，由 `database_url` 配置）

---

## 1. 表结构

### 1.1 `documents` — 文档主表

存储上传文档的元数据信息。

| 列名 | 类型 | 约束 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | UUID | PK | `uuid4()` | 主键，应用层生成 |
| name | VARCHAR(512) | NOT NULL | — | 文件名 |
| file_hash | VARCHAR(64) | UNIQUE, INDEX | — | 文件 SHA-256，用于文件级去重 |
| mime_type | VARCHAR(128) | NOT NULL | — | MIME 类型，如 `application/pdf` |
| size | BIGINT | NOT NULL | — | 文件大小（字节），支持 >2GB |
| storage_provider | VARCHAR(32) | NOT NULL | `'cos'` | 存储提供商 |
| cos_bucket | VARCHAR(128) | NOT NULL | — | COS 存储桶名称 |
| cos_object_key | VARCHAR(512) | NOT NULL | — | COS 对象路径 |
| cos_region | VARCHAR(64) | NOT NULL | — | COS 地域，如 `ap-guangzhou` |
| status | VARCHAR(32) | NOT NULL | `'uploading'` | 文档状态（见枚举） |
| error_message | TEXT | NULLABLE | — | 失败时的错误信息 |
| created_at | TIMESTAMPTZ | NOT NULL | `NOW()` | 创建时间，数据库生成 |
| updated_at | TIMESTAMPTZ | NOT NULL | `NOW()` | 更新时间，自动刷新 |

**索引：**
- 主键：`id`
- 唯一索引：`file_hash`
- 外键关联：`document_chunks.document_id → documents.id`

---

### 1.2 `document_chunks` — 文档片段表

存储文档切分后的文本块及其向量嵌入。

| 列名 | 类型 | 约束 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | UUID | PK | `uuid4()` | 主键 |
| document_id | UUID | FK, NOT NULL, INDEX | — | 所属文档，级联删除 |
| content | TEXT | NOT NULL | — | 原文片段 |
| embedding | vector(1024) | NOT NULL | — | 向量嵌入，维度由配置控制 |
| page_no | INTEGER | NULLABLE | — | 页码（若有） |
| section_path | VARCHAR(1024) | NULLABLE | — | 章节路径 |
| chunk_index | INTEGER | NOT NULL | — | 块序号，文档内排序 |
| chunk_hash | VARCHAR(32) | INDEX | — | 内容 MD5，增量索引用 |
| metadata | JSONB | NOT NULL | `'{}'` | 额外元数据 |
| created_at | TIMESTAMPTZ | NOT NULL | `NOW()` | 创建时间 |

**索引：**
- 主键：`id`
- 外键索引：`document_id`
- 普通索引：`chunk_hash`

**外键约束：**
- `document_id → documents(id) ON DELETE CASCADE`
- 删除文档时，数据库自动删除所有关联 chunks

---

## 2. 状态枚举

`documents.status` 字段取值：

| 值 | 阶段 | 说明 |
|----|------|------|
| `uploading` | 上传中 | 文件已写入 COS，尚未入库 |
| `parsing` | 解析中 | 正在解析文档内容 |
| `indexing` | 索引中 | 正在切分、向量化、写入 chunks |
| `ready` | 就绪 | 处理完成，可被检索 |
| `failed` | 失败 | 任意阶段发生错误 |

生命周期流转：

```
uploading → parsing → indexing → ready
                                        ↘
                                failed（任意阶段）
```

---

## 3. 关联关系

```
documents (1) ──── (N) document_chunks
```

- `Document` 与 `DocumentChunk` 是一对多关系
- 通过 `document_id` 外键关联
- `ON DELETE CASCADE`：删除文档时自动级联删除所有关联 chunks
- `passive_deletes=True`：SQLAlchemy 不逐条删除，交由数据库处理，性能更优

---

## 4. 配置参数

来自 `app.core.config.Settings`，影响数据库行为：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `database_url` | `postgresql+asyncpg://rag:rag@localhost:5432/rag_kb` | 数据库连接串 |
| `embedding_dim` | 1024 | 向量维度，与 pgvector 的 vector(n) 一致 |
| `chunk_size` | 600 | 文档切分块大小（字符数） |
| `chunk_overlap` | 60 | 切分重叠窗口（字符数） |

---

## 5. 建表 SQL

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(512) NOT NULL,
    file_hash VARCHAR(64) NOT NULL UNIQUE,
    mime_type VARCHAR(128) NOT NULL,
    size BIGINT NOT NULL,
    storage_provider VARCHAR(32) NOT NULL DEFAULT 'cos',
    cos_bucket VARCHAR(128) NOT NULL,
    cos_object_key VARCHAR(512) NOT NULL,
    cos_region VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'uploading',
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    embedding vector(1024) NOT NULL,
    page_no INTEGER,
    section_path VARCHAR(1024),
    chunk_index INTEGER NOT NULL,
    chunk_hash VARCHAR(32) NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_document_chunks_document_id ON document_chunks(document_id);
CREATE INDEX idx_document_chunks_chunk_hash ON document_chunks(chunk_hash);
```

---

## 6. 查询示例

**按文件 hash 去重查询：**
```sql
SELECT id FROM documents WHERE file_hash = :file_hash;
```

**查询文档的所有 chunks：**
```sql
SELECT * FROM document_chunks WHERE document_id = :doc_id ORDER BY chunk_index;
```

**向量相似度搜索（余弦距离）：**
```sql
SELECT * FROM document_chunks
ORDER BY embedding <=> :query_vector
LIMIT 10;
```

**带文档过滤的向量搜索：**
```sql
SELECT dc.* FROM document_chunks dc
JOIN documents d ON d.id = dc.document_id
WHERE d.status = 'ready'
ORDER BY dc.embedding <=> :query_vector
LIMIT 10;
```