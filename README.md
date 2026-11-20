# NAS 服務導覽首頁 — Homepage（Synology DS718+ 2GB 最佳化版）

專為 **Synology DS718+（原廠 2GB RAM、純 HDD 無 SSD、搭配 Tailscale）** 設計的私人服務入口儀表板（適用 Homepage `v2.8+`），預先整合 `Synology DSM`、`Vaultwarden`、`LibreTV`、`雲端書閣 Novel` 與 `Uptime Kuma`。

部署架構延續 [`Johntsai0320/vaultwarden-backup-`](https://github.com/Johntsai0320/vaultwarden-backup-) 的 `.env` 集中管理與 Synology Container Manager 專案規範。

---

## 📁 目錄結構

```text
/volume1/docker/homepage/
├── .env.example
├── .gitignore
├── README.md
├── docker-compose.yml
└── config/
    ├── bookmarks.yaml
    ├── services.yaml
    ├── settings.yaml
    └── widgets.yaml
```

---

## ✨ 針對 DS718+ 2GB RAM 的調校設計

1. **嚴格記憶體上限**：容器限制 `mem_limit: 192m`（`memswap_limit: 256m`）搭配 `NODE_OPTIONS=--max-old-space-size=128`，確保不排擠 DSM 與 Vaultwarden 記憶體，避免 HDD Swap 卡頓。
2. **避開現有服務埠號**：映射到 NAS **`3010`**（避開 `novel:3000`、`uptime-kuma:3001`、`LibreTV:8080`、`vaultwarden:8200`、`nginx:8088/8443`）。
3. **保護 HDD 與安全隔離**：不掛載 `/var/run/docker.sock` 降低輪詢與提權風險；資源小工具輪詢間隔調整為 `15000ms`（15 秒），並停用 Synology Btrfs RAID 不支援的 `disk` 讀取；啟用日誌輪替（`5m × 2`）。
4. **Tailscale 整合與隱私保護**：透過 `HOMEPAGE_VAR_*` 注入各服務網址於 `.env`，私網與 Tailscale IP 不進 Git 版控。

---

## 🚀 部署步驟（目標路徑：`/volume1/docker/homepage`）

1. 透過 SSH 連線到 NAS，將專案下載至 `/volume1/docker/homepage`（或直接下載 ZIP 解壓縮至該目錄）：
   ```bash
   git clone https://github.com/Johntsai0320/homepage.git /volume1/docker/homepage
   cd /volume1/docker/homepage
   ```
2. 複製環境變數範本並編輯：
   ```bash
   cp .env.example .env
   ```
   - 務必修改 `HOMEPAGE_ALLOWED_HOSTS` 加入您的 **NAS 區網 IP:3010** 與 **Tailscale IP:3010**（或 MagicDNS 名稱，以逗號分隔且**勿留空白**），否則 Homepage v2 會拒絕連線並於 log 顯示 `Host validation failed` 錯誤。
   - 更新 `HOMEPAGE_VAR_*` 為對應的區網或 Tailscale 位址。
3. 開啟 DSM **Container Manager → 專案 (Project) → 新增**，選擇路徑 `/docker/homepage` 並以現有 `docker-compose.yml` 啟動（或透過 SSH 執行 `docker compose pull && docker compose up -d`）。
4. 連上 Tailscale 後於瀏覽器開啟 `http://<您的Tailscale_IP>:3010` 即可使用。

---

## 🔗 啟用 Uptime Kuma 首頁狀態小工具（選用）

1. 在 Uptime Kuma 新增一個 **狀態頁 (Status Page)**，設定 URL slug（例如 `nas`）並加入想展示的監控項目。
2. 編輯 `config/services.yaml`，將 `Uptime Kuma` 底下的 `widget:` 區塊取消註解，確認 `slug` 一致後存檔即可即時更新（Homepage 透過 `host.docker.internal:3001` 本機直連，無需走外網）。
