#自定义 PostgreSQL 镜像:pgvector +zhparser(中文全文检索)
#
# 社区没有同时维护 pgvector + zhparser 的官方镜像,所以用多阶段构建:
#- builder 阶段在 postgres:16-bookworm 上编译 SCWS 与 zhparser
#- 运行阶段直接基于 pgvector/pgvector:pg16,把 zhparser 产物拷过去
# 学员只需`docker compose up -d --build` 一次即可同时拿到两个扩展。

ARG PG_MAJOR=16

FROM postgres:${PG_MAJOR}-bookworm AS builder

ARG PG_MAJOR
# Bookworm 使用 DEB822 格式(.sources),不再有 /etc/apt/sources.list
RUN sed -i \
    -e 's|http://deb.debian.org/debian|http://mirrors.aliyun.com/debian|g' \
    -e 's|http://apt.postgresql.org/pub/repos/apt|http://mirrors.aliyun.com/postgresql/repos/apt|g' \
    /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
        postgresql-server-dev-${PG_MAJOR} \
    && rm -rf /var/lib/apt/lists/*

# SCWS:zhparser 的底层中文分词库
COPY dockerassets/scws-1.2.3.tar.bz2 /tmp/scws.tar.bz2
RUN mkdir -p /tmp/scws \
    && tar -xjf /tmp/scws.tar.bz2 -C /tmp/scws --strip-components=1 \
    && cd /tmp/scws \
    && ./configure \
    && make -j"$(nproc)" \
    && make install

# zhparser:基于 SCWS 的 PostgreSQL 中文全文检索扩展
COPY dockerassets/pg_zhparser.tar.gz /tmp/zhparser.tar.gz
RUN mkdir -p /tmp/zhparser \
    && tar -xzf /tmp/zhparser.tar.gz -C /tmp/zhparser --strip-components=1 \
    && cd /tmp/zhparser \
    && make \
    && make install

FROM pgvector/pgvector:pg16

ARG PG_MAJOR=16

# 拷贝 zhparser 编译产物:动态库 +扩展元数据 +词典文件
COPY --from=builder /usr/lib/postgresql/${PG_MAJOR}/lib/zhparser.so \
    /usr/lib/postgresql/${PG_MAJOR}/lib/
COPY --from=builder /usr/local/lib/libscws.* /usr/local/lib/
COPY --from=builder /usr/share/postgresql/${PG_MAJOR}/extension/zhparser* \
    /usr/share/postgresql/${PG_MAJOR}/extension/
COPY --from=builder /usr/share/postgresql/${PG_MAJOR}/tsearch_data/ \
    /usr/share/postgresql/${PG_MAJOR}/tsearch_data/

#让 ld 能找到/usr/local/lib 下的 libscws.so
RUN ldconfig
