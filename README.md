# SUTK 修改器（便携版）

针对 **Seres Universalis: Three Kingdoms（Demo）** 的存档修改工具。只读写 `%LOCALAPPDATA%\ProjectA\Saved\Saves` 下的 `.sav`，**不修改游戏本体**。

本仓库提供两种使用方式：

| 方式 | 适合谁 | 入口 | 说明文档 |
|------|--------|------|----------|
| **桌面版（推荐）** | 日常改档、城市/武将/编队 | `desktop-app\dist\SUTK修改器\SUTK修改器.exe` | [桌面版使用说明.md](./桌面版使用说明.md) |
| **控制台版** | 热键呼出、命令行、老习惯 | `1 安装.bat` / `控制台.bat` | [安装教程.txt](./安装教程.txt)、[使用说明.md](./使用说明.md) |

---

## 文档索引

| 文档 | 内容 |
|------|------|
| [桌面版使用说明.md](./桌面版使用说明.md) | 图形界面：存档、模块、城市、编队、外交、检查、设置 |
| [安装教程.txt](./安装教程.txt) | 控制台版：安装、热键、模块勾选、城市归属 |
| [使用说明.md](./使用说明.md) | 控制台版功能参考、模块说明、审计与历史版本 |
| [经验总结.md](./经验总结.md) | 踩坑与存档不变量（桌面版「说明」页也会加载） |
| [desktop-app/打包说明.md](./desktop-app/打包说明.md) | 如何打出 `dist\SUTK修改器` 便携文件夹 |
| [desktop-app/开发说明.md](./desktop-app/开发说明.md) | 前端 Vue + Python API + Tauri 本地调试 |
| [desktop-app/发给别人.txt](./desktop-app/发给别人.txt) | 发给他人时的简短说明 |

---

## 桌面版快速开始

1. 进入 `desktop-app\dist\SUTK修改器\`（或自己打包后的同名文件夹）。
2. 双击 **`SUTK修改器.exe`**（需系统已带 **WebView2**，Win10/11 一般已有）。
3. 顶部选择存档 → **存档** 页勾选模块 → **应用修改**。
4. 进游戏 **退出到主菜单并重新读档** 后生效。

配置、备份、历史默认写在 **exe 同目录**（`config.json`、`backup\`、`history\`），与控制台版逻辑共用 `SUTKMod.pyw`。

---

## 目录结构（开发者）

```
SUTK修改器_便携版/
├── SUTKMod.pyw          # 存档读写与补丁核心
├── MemScan.py           # 内存扫描（可选，需管理员）
├── config.json          # 模块/上限/编队预设等（运行时可生成）
├── python/              # 嵌入式 Python（控制台版与桌面版共用）
├── desktop/
│   ├── server.py        # 本地 HTTP API（127.0.0.1）
│   ├── names_zh.json    # 武将中文名表
│   ├── cities_zh.json   # 城市中文名表
│   ├── troop_kinds_zh.json  # 兵种 ID → 中文名
│   ├── static/          # Vite 构建产物
│   ├── web/             # Vue 3 源码
│   └── tools/           # repak、兵种表生成脚本等
└── desktop-app/
    ├── src-tauri/       # Tauri 壳
    ├── 打包.ps1
    └── dist/SUTK修改器/ # 打包输出
```

---

## 常见问题（共用）

- **改了游戏里没变**：必须重新读档，不能只在当前战役里继续玩。
- **游戏正在运行**：多数写入会提示读档后生效；极端情况请先存盘并回主菜单再改。
- **杀毒误报**：本地 Python + 自打包 exe 较常见；工具不联网改游戏文件。

更细的 FAQ 见各使用说明文档。
