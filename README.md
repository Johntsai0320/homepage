# NAS 服務導覽首頁 — Homepage（Synology DS718+ 2GB 最佳化版）

專為 **Synology DS718+（原廠 2GB RAM、純 HDD 無 SSD、搭配 Tailscale）** 設計的私人服務入口儀表板（基於 Homepage `v2.8+`），預先整合 `Synology DSM`、`Vaultwarden`、`LibreTV`、`雲端書閣 Novel` 與 `Uptime Kuma`。

部署架構整合了 [`Johntsai0320/LibreTV`](https://github.com/Johntsai0320/LibreTV) 的 **GitHub Actions 自動發布多架構 GHCR 映像檔（`.env` + `ghcr.io`）** 與 [`Johntsai0320/novel`](https://github.com/Johntsai0320/novel) 的 **`docker-compose.yml` + `synology-docker-config.json` 雙模式部署**。

---

## 📁 目錄結構

```text
/volume1/docker/homepage/
├── .dockerignore
├── .env.example
├── .gitignore
├── Dockerfile
├── README.md
├── docker-compose.yml
├── docker-entrypoint-nas.sh
├── synology-docker-config.json
├── .github/workflows/
│   └── docker-publish.yml
├── config/
│   ├── bookmarks.yaml
│   ├── services.yaml
│   ├── settings.yaml
│   └── widgets.yaml
└── tests/
    └── test_homepage_init.py
```

---

## ✨ 針對 DS718+ 2GB RAM 的調校與部署設計

1. **嚴格記憶體上限**：容器限制 `mem_limit: 192m`（`memswap_limit: 256m`）搭配 `NODE_OPTIONS=--max-old-space-size=128`，確保不排擠 DSM 與 Vaultwarden 記憶體，避免 HDD Swap 卡頓。
2. **避開現有服務埠號**：映射到 NAS **`3010`**（避開 `novel:3000`、`uptime-kuma:3001`、`LibreTV:8080`、`vaultwarden:8200`、`nginx:8088/8443`）。
3. **保護 HDD 與安全隔離**：不掛載 `/var/run/docker.sock` 降低輪詢與提權風險；資源小工具輪詢間隔調整為 `15000ms`（15 秒），停用 Synology Btrfs RAID 不支援的 `disk` 讀取，並啟用日誌輪替（`5m × 2`）。
4. **開箱即用預設範本＋不覆蓋自訂**：自訂映像檔內建針對 DS718+ 調校的 `config/*.yaml` 範本；若掛載的 `./config` 資料夾為空，首次啟動會自動補齊預設檔，**已有自訂設定則完整保留不覆蓋**。
5. **Tailscale 整合與隱私保護**：透過 `HOMEPAGE_VAR_*` 注入各服務網址於 `.env` 或 Container Manager 環境變數，私網與 Tailscale IP 不進 Git 版控。

---

## 🚀 部署方式一：Synology Container Manager 專案 / Docker Compose（最推薦）

1. 透過 SSH 連線到 NAS，下載專案至 `/volume1/docker/homepage`：
   ```bash
   git clone https://github.com/Johntsai0320/homepage.git /volume1/docker/homepage
   cd /volume1/docker/homepage
   cp .env.example .env
   ```
2. 編輯 `.env`：
   - **務必修改 `HOMEPAGE_ALLOWED_HOSTS`** 加入您的 **NAS 區網 IP:3010** 與 **Tailscale IP:3010**（或 MagicDNS 名稱，以逗號分隔且**勿留空白**），否則 Homepage v2 會拒絕連線並於 log 顯示 `Host validation failed` 錯誤。
   - 更新 `HOMEPAGE_VAR_*` 為對應的區網或 Tailscale 位址。
3. 啟動服務（二選一）：
   - **Docker Compose CLI**（直接拉取 GHCR 映像檔，零建置）：
     ```bash
     docker compose pull && docker compose up -d
     ```
     > **提示**：若要在 NAS 本地從 `Dockerfile` 建置映像，可執行 `docker compose up -d --build`。
   - **Synology Container Manager 圖形介面**：開啟 **Container Manager → 專案 (Project) → 新增**，路徑選擇 `/docker/homepage` 並以現有 `docker-compose.yml` 啟動。
4. 連上 Tailscale 後於瀏覽器開啟 `http://<您的Tailscale_IP>:3010` 即可使用。

---

## 📦 部署方式二：Synology Container Manager 匯入 `synology-docker-config.json`

1. 先於 Synology Container Manager 的 **「映像檔」** 下載：
   `ghcr.io/johntsai0320/homepage:latest`
2. 在 File Station 建立空白目錄：
   `/docker/homepage/config`
   （首次啟動容器時，會自動將預設 `settings.yaml`、`widgets.yaml`、`services.yaml`、`bookmarks.yaml` 寫入此目錄，免手動複製檔案。）
3. 進入 **Container Manager → 容器 → 設定 → 匯入設定**，選擇本專案的 [`synology-docker-config.json`](./synology-docker-config.json)。
4. 啟動前於容器的 **環境變數** 分頁修改 `HOMEPAGE_ALLOWED_HOSTS` 與各 `HOMEPAGE_VAR_*` 位址。
   > 若希望重啟容器時直接從 GitHub `main` 拉取最新 `config/*.yaml` 範本（注意會覆蓋同名 YAML 檔），可將 `AUTO_SYNC_GITHUB` 設為 `true`。

---

## ⚙️ 環境變數一覽

| 變數名稱 | 預設值 | 說明 |
| :--- | :--- | :--- |
| `HOMEPAGE_IMAGE` | `ghcr.io/johntsai0320/homepage:latest` | Docker Compose 使用的映像檔位址／版本標籤 |
| `HOMEPAGE_BIND_IP` / `HOMEPAGE_PORT` | `0.0.0.0` / `3010` | NAS 宿主機對應容器 `3000` 的綁定 IP 與埠號 |
| `TZ` | `Asia/Taipei` | 容器時區 |
| `NODE_OPTIONS` | `--max-old-space-size=128` | Node.js V8 記憶體上限，防止 2GB RAM 機型 OOM |
| `HOMEPAGE_ALLOWED_HOSTS` | `localhost:3010,127.0.0.1:3010` | 允許連線的 Host 清單（逗號分隔、勿留空白，務必補上區網與 Tailscale IP:3010） |
| `HOMEPAGE_VAR_NAS_HOST` | `192.168.1.100` | Synology DSM 主機位址 |
| `HOMEPAGE_VAR_DSM_PORT` | `5001` | Synology DSM HTTPS 埠號 |
| `HOMEPAGE_VAR_LIBRETV_URL` | `http://192.168.1.100:8080` | LibreTV 服務入口網址 |
| `HOMEPAGE_VAR_NOVEL_URL` | `http://192.168.1.100:3000` | 雲端書閣 Novel 服務入口網址 |
| `HOMEPAGE_VAR_VAULTWARDEN_URL` | `http://192.168.1.100:8200` | Vaultwarden 服務入口網址 |
| `HOMEPAGE_VAR_UPTIME_KUMA_URL` | `http://192.168.1.100:3001` | Uptime Kuma 服務入口網址 |
| `AUTO_SYNC_GITHUB` | `false` | 啟動時是否從 GitHub 同步最新 `config/*.yaml` |
| `GITHUB_REPO` / `GITHUB_BRANCH` | `https://github.com/Johntsai0320/homepage.git` / `main` | 同步來源倉庫與分支 |

---

## 🔗 啟用 Uptime Kuma 首頁狀態小工具（選用）

1. 在 Uptime Kuma 新增一個 **狀態頁 (Status Page)**，設定 URL slug（例如 `nas`）並加入想展示的監控項目。
2. 編輯 `/docker/homepage/config/services.yaml`，將 `Uptime Kuma` 底下的 `widget:` 區塊取消註解，確認 `slug` 一致後存檔即可即時更新：
   - 若透過 **`docker-compose.yml`** 部署，保留 `url: http://host.docker.internal:3001` 即可本機直連。
   - 若透過 **方式二（GUI 匯入單一容器）** 部署，因單容器未注入 `host.docker.internal`，請將 widget 的 `url` 改為 `http://<您的NAS區網IP>:3001`。

---

## 🧪 本機測試與 GitHub Actions 自動發布

執行設定檔、環境變數一致性與啟動腳本單元測試：

```bash
python3 -m unittest discover -s tests -v
```

每次推送至 `main` 分支或推送 `v*` 版本標籤時，[`.github/workflows/docker-publish.yml`](./.github/workflows/docker-publish.yml) 會先執行單元測試與真實容器 `/api/healthcheck` 煙霧測試，通過後自動建置 `linux/amd64` 與 `linux/arm64` 多架構映像檔並發布至 `ghcr.io/johntsai0320/homepage:latest`。

> **注意**：首次發布 GHCR 套件後，請至 GitHub **Packages → homepage → Package settings** 確認套件存取權限（設為 Public 或關聯至本倉庫），即可在 NAS 免登入直接拉取映像檔。
