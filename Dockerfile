FROM ghcr.io/gethomepage/homepage:latest

# 安裝 git 與 ca-certificates，支援選用的 AUTO_SYNC_GITHUB 啟動同步設定
RUN apk add --no-cache git ca-certificates

# 預置針對 Synology DS718+ 調校的預設設定範本（僅在目標檔案不存在時自動補齊）
COPY config /opt/homepage-defaults/config
COPY docker-entrypoint-nas.sh /usr/local/bin/docker-entrypoint-nas.sh

RUN chmod +x /usr/local/bin/docker-entrypoint-nas.sh && \
    mkdir -p /opt/repo-sync

ENV TZ=Asia/Taipei
ENV NODE_OPTIONS=--max-old-space-size=128

ENTRYPOINT ["/usr/local/bin/docker-entrypoint-nas.sh"]
CMD ["node", "server.js"]
