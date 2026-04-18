# Render 部署說明

這個專案已經補好兩個 Render 需要的東西：

- `Procfile`：本機/Render 都可以用 `gunicorn app:app` 啟動
- `render.yaml`：預設把會員下載檔案與 SQLite 資料掛到持久化磁碟

## 下載檔案資料夾

- 預設資料夾是 `member_files/`
- 管理員新增商品時，`file_path` 請填相對路徑，例如：
  - `member_files/Git_Tutorial_1.pdf`
  - `member_files/subfolder/manual.pdf`

## Render 環境變數

如果你不用 `render.yaml`、而是手動在 Render Dashboard 建服務，至少要設定：

- `SECRET_KEY`
- `DATABASE_URL`
- `MEMBER_FILES_DIR`

範例：

- `MEMBER_FILES_DIR=/opt/render/project/src/data/member_files`
- `DATABASE_URL=sqlite:////opt/render/project/src/data/member.db`

## 注意

Render 的檔案系統預設是暫時性的。若你要讓會員檔案部署後還在，請保留持久化磁碟設定，否則重開機或重部署後檔案會消失。
