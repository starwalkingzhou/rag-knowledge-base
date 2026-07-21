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
- **向量索引:** `ix_document_chunks_embedding_hnsw` — pgvector HNSW,`vector_cosine_ops`(余弦距离),`m/ef_construction` 用默认值

**外键约束：**
- `document_id → documents(id) ON DELETE CASCADE`
- 删除文档时，数据库自动删除所有关联 chunks

---

### 1.3 `conversations` — 会话主表

多轮问答的会话容器,每次新建会话对应一行。

| 列名 | 类型 | 约束 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | UUID | PK | `uuid4()` | 主键 |
| title | VARCHAR(256) | NOT NULL | `'新对话'` | 会话标题 |
| created_at | TIMESTAMPTZ | NOT NULL | `NOW()` | 创建时间 |
| updated_at | TIMESTAMPTZ | NOT NULL | `NOW()` | 更新时间,自动刷新 |

**索引:**
- 主键:`id`

> 预留:后续接入用户体系时会追加 `user_id` 列。

---

### 1.4 `messages` — 消息表

一轮问答产生的一条消息(user / assistant / system)。

| 列名 | 类型 | 约束 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | UUID | PK | `uuid4()` | 主键 |
| conversation_id | UUID | FK, NOT NULL, INDEX | — | 所属会话,级联删除 |
| role | VARCHAR(16) | NOT NULL | — | 角色:`user` / `assistant` / `system` |
| content | TEXT | NOT NULL | — | 消息正文 |
| metadata | JSONB | NOT NULL | `'{}'` | 扩展字段:model / token / latency 等 |
| created_at | TIMESTAMPTZ | NOT NULL | `NOW()` | 创建时间 |

**索引:**
- 主键:`id`
- 外键索引:`conversation_id`

**外键约束:**
- `conversation_id → conversations(id) ON DELETE CASCADE`

---

### 1.5 `answer_citations` — 回答引用快照

assistant 消息引用的 chunk 快照。**冗余持久化文档名 / 页码 / 引文**,保证 chunk 被覆盖或文档被删后,历史会话仍可展示当时的引用原文。

| 列名 | 类型 | 约束 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | UUID | PK | `uuid4()` | 主键 |
| message_id | UUID | FK, NOT NULL, INDEX | — | 所属 assistant 消息,级联删除 |
| ordinal | INTEGER | NOT NULL | — | prompt 中的「片段 N」编号,从 1 开始 |
| document_id | UUID | FK, NULLABLE | — | 源文档,原文档被删则置 NULL |
| chunk_id | UUID | FK, NULLABLE | — | 源 chunk,被覆盖 / 删除则置 NULL |
| document_name | VARCHAR(512) | NOT NULL | — | 文档名快照 |
| page_no | INTEGER | NULLABLE | — | 页码快照 |
| quote | TEXT | NOT NULL | — | 引文原文快照 |

**索引:**
- 主键:`id`
- 外键索引:`message_id`

**外键约束:**
- `message_id → messages(id) ON DELETE CASCADE`
- `document_id → documents(id) ON DELETE SET NULL`
- `chunk_id → document_chunks(id) ON DELETE SET NULL`

> 为什么用 `ordinal` 而不是靠 `id` 排序:UUID 是随机的无法用于排序,而 prompt 里给 LLM 看的「片段 N」编号必须持久化,才能保证刷新后引用顺序与 LLM 当时看到的一致。

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

`messages.role` 字段取值:

| 值 | 说明 |
|----|------|
| `user` | 用户输入 |
| `assistant` | LLM 回答 |
| `system` | 系统提示 |

---

## 3. 关联关系

```
documents (1) ──── (N) document_chunks
                                │
                                │ (可空引用,SET NULL)
                                ▼
conversations (1) ── (N) messages (1) ── (N) answer_citations
                                                     │
                                                     └──▶ documents (可空,SET NULL)
```

**文档侧:**
- `Document` ↔ `DocumentChunk` 一对多,`ON DELETE CASCADE`
- `passive_deletes=True`:SQLAlchemy 不逐条删除,交由数据库处理

**会话侧:**
- `Conversation` ↔ `Message` 一对多,`ON DELETE CASCADE`
- `Message` ↔ `AnswerCitation` 一对多,`ON DELETE CASCADE`(assistant 消息才有引用)

**跨域引用(引用快照):**
- `AnswerCitation.document_id → documents.id` `ON DELETE SET NULL`
- `AnswerCitation.chunk_id → document_chunks.id` `ON DELETE SET NULL`
- 文档 / chunk 被删除后,引用记录仍保留,通过冗余的 `document_name / page_no / quote` 展示历史内容

---

## 4. 配置参数

来自 `app.core.config.Settings`，影响数据库行为：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `database_url` | `postgresql+asyncpg://rag:rag@localhost:5432/rag_kb` | 数据库连接串 |
| `embedding_dim` | 1024 | 向量维度，与 pgvector 的 vector(n) 一致 |
| `chunk_size` | 600 | 文档切分块大小（字符数） |
| `chunk_overlap` | 60 | 切分重叠窗口（字符数） |
| `retrieval_top_k` | 5 | 向量检索 Top-K,交给 LLM 的候选 chunk 数 |
| `retrieval_min_score` | 0.6 | 拒答阈值:Top-K 最高分低于此值直接拒答 |
| `chat_history_window` | 5 | 多轮窗口:塞进 prompt 的历史轮数 |

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

-- pgvector HNSW 索引(cosine 距离),向量检索走此索引
CREATE INDEX ix_document_chunks_embedding_hnsw
    ON document_chunks USING hnsw (embedding vector_cosine_ops);

-- 聊天相关表
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(256) NOT NULL DEFAULT '新对话',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(16) NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_messages_conversation_id ON messages(conversation_id);

CREATE TABLE answer_citations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
    chunk_id UUID REFERENCES document_chunks(id) ON DELETE SET NULL,
    document_name VARCHAR(512) NOT NULL,
    page_no INTEGER,
    quote TEXT NOT NULL
);
CREATE INDEX ix_answer_citations_message_id ON answer_citations(message_id);
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

**查询会话及其消息(按时间正序):**
```sql
SELECT * FROM messages
WHERE conversation_id = :conv_id
ORDER BY created_at ASC;
```

**查询某条 assistant 消息的引用(按 ordinal 排序):**
```sql
SELECT * FROM answer_citations
WHERE message_id = :msg_id
ORDER BY ordinal ASC;
```

---

## 7. 迁移历史

Alembic 迁移链(`backend/alembic/versions/`):

| Revision | 说明 |
|----------|------|
| `ac611d4b45b9` | init: `documents` + `document_chunks` |
| `4a73abaf8d87` | add chat tables (`conversations` / `messages` / `answer_citations`) + pgvector HNSW 索引 |

常用命令(在 `backend/` 目录下):
```bash
alembic upgrade head       # 应用到最新
alembic downgrade -1       # 回滚一步
alembic current            # 查看当前版本
alembic history            # 查看迁移链
```