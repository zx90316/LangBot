# Windows 本地開發與換機指南

本文件說明如何在 **Windows** 上運行 LangBot，並使用 repo 內建的 **langbot-plugin 本地 patch**，無需修改 PyPI 上游 SDK。

## 背景

在 Windows 上，Plugin Runtime 的安裝 worker 有幾個上游尚未修復的問題：

| 現象 | 原因 |
|------|------|
| `WinError 10106` | 子程序環境缺少 `SystemRoot` 等 Windows 必需變數 |
| `WinError 6`（stdio pipe） | asyncio 在 Windows 不支援 Plugin worker 的 stdio 傳輸 |
| `ModuleNotFoundError`（如 `pillowmd`） | oss_dev 路徑啟動 worker 前未自動安裝 `requirements.txt` |
| Banner `UnicodeEncodeError` | 終端機 cp950 無法輸出 emoji |

Box 沙箱在 Windows 本地另有 stdio 問題；本指南 **維持關閉 Box**（`box.enabled: false` 或啟動腳本 env 覆寫）。

## Patch 機制

修補檔位於：

```
patches/langbot-plugin/0.5.5/
  MANIFEST.json
  runtime/plugin/mgr.py
  runtime/plugin/worker_launcher.py
  runtime/app.py
```

對應 [`pyproject.toml`](../pyproject.toml) 中的 `langbot-plugin==0.5.5`。

**重要：** 每次執行 `uv sync` 後，`.venv` 會還原上游套件，必須重新套用 patch。

## 首次安裝

```powershell
cd D:\LangBot-Windows
uv sync --dev
.\scripts\start-langbot.ps1
```

或分步執行：

```powershell
uv sync --dev
uv run --no-sync python scripts/apply-langbot-plugin-patches.py
$env:PYTHONIOENCODING = "utf-8"
$env:BOX__ENABLED = "false"
uv run --no-sync main.py
```

Web UI 預設：`http://127.0.0.1:5300`

## 換機 / 複製專案

1. 複製整個 repo（含 `patches/`、`scripts/`；`data/` 可選，保留設定與資料庫）
2. 在新機器安裝 Python 3.11+ 與 [uv](https://docs.astral.sh/uv/)
3. 執行：

```powershell
cd D:\LangBot-Windows
uv sync --dev
.\scripts\start-langbot.ps1
```

若需同步依賴並啟動：

```powershell
.\scripts\start-langbot.ps1 -Sync
```

Linux / WSL 對等命令：

```bash
./scripts/start-langbot.sh
# 或
./scripts/start-langbot.sh --sync
```

## 驗證 patch 是否已套用

```powershell
uv run --no-sync python scripts/apply-langbot-plugin-patches.py --check
```

成功時輸出：`Patch check OK (3 files match langbot-plugin 0.5.5).`

## Plugin 依賴

Patch 會在啟動 installation worker **之前** 對 artifact 目錄執行 `install_requirements_isolated()`（寫入 Plugin 專屬 `.venv`）。

若個別套件仍缺失，可手動安裝到 LangBot 環境：

```powershell
uv pip install <package-name>
```

## 常見問題

### `data/temp/lbp` 權限錯誤（WinError 5）

通常是先前程序損壞了目錄 ACL。在 **LangBot 完全停止** 後：

```powershell
Rename-Item data\temp data\temp.broken -ErrorAction SilentlyContinue
```

下次啟動會自動重建 `data/temp/lbp`。

### `uv sync` 後 Plugin 又壞了

重新套用 patch：

```powershell
uv run --no-sync python scripts/apply-langbot-plugin-patches.py
```

或使用 `.\scripts\start-langbot.ps1`（會自動 apply）。

### langbot-plugin 版本升級

若 `pyproject.toml` 中 `langbot-plugin` 版本不再是 `0.5.5`：

1. 在 `patches/langbot-plugin/<新版本>/` 建立對應 patch（或從上游重新移植修復）
2. 更新該目錄的 `MANIFEST.json`
3. 執行 apply 腳本；版本不匹配時會明確報錯

## 相關腳本

| 腳本 | 用途 |
|------|------|
| [`scripts/apply-langbot-plugin-patches.py`](../scripts/apply-langbot-plugin-patches.py) | 將 patch 覆蓋到 `.venv` |
| [`scripts/apply-langbot-plugin-patches.ps1`](../scripts/apply-langbot-plugin-patches.ps1) | PowerShell 包裝 |
| [`scripts/start-langbot.ps1`](../scripts/start-langbot.ps1) | Windows 一鍵 apply + 啟動 |
| [`scripts/start-langbot.sh`](../scripts/start-langbot.sh) | Unix/WSL 一鍵 apply + 啟動 |
