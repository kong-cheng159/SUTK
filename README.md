# SUTK 修改器（便携版）

针对 **Seres Universalis: Three Kingdoms（Demo）** 的存档修改工具。只读写 `%LOCALAPPDATA%\ProjectA\Saved\Saves` 下的 `.sav`，**不修改 Steam 游戏安装目录**（路径说明见 [docs/游戏与路径.md](./docs/游戏与路径.md)）。

本仓库提供两种使用方式：

| 方式 | 适合谁 | 入口 | 说明文档 |
|------|--------|------|----------|
| **桌面版（推荐）** | 日常改档、城市/武将/编队 | `desktop-app\dist\SUTK修改器\SUTK修改器.exe` | [docs/桌面版使用说明.md](./docs/桌面版使用说明.md) |
| **控制台版** | 热键呼出、命令行、老习惯 | `1 安装.bat` / `控制台.bat` | [docs/安装教程.txt](./docs/安装教程.txt)、[docs/使用说明.md](./docs/使用说明.md) |

另有独立子项目 **[华夏风云控制台修改器](./contrib/hxfs-save-editor/)**（见 [contrib/README.md](./contrib/README.md)）。

---

## 文档索引

完整列表见 **[docs/README.md](./docs/README.md)**。

| 文档 | 内容 |
|------|------|
| [docs/桌面版使用说明.md](./docs/桌面版使用说明.md) | 图形界面：存档、模块、城市、编队、外交、检查、设置 |
| [docs/安装教程.txt](./docs/安装教程.txt) | 控制台版：安装、热键、模块勾选 |
| [docs/使用说明.md](./docs/使用说明.md) | 控制台版功能参考、模块说明 |
| [docs/经验总结.md](./docs/经验总结.md) | 踩坑与存档不变量 |
| [desktop-app/打包说明.md](./desktop-app/打包说明.md) | 打出 `dist\SUTK修改器` |
| [desktop-app/开发说明.md](./desktop-app/开发说明.md) | Vue + Python API + Tauri |

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
├── README.md
├── SUTKMod.pyw              # 存档读写与补丁核心
├── MemScan.py               # 内存扫描（可选，需管理员）
├── config.json
├── 1 安装.bat / 控制台.bat   # 控制台版入口（须在根目录）
├── python/                  # 嵌入式 Python
├── docs/                    # 用户文档
├── contrib/                 # 附属工具（如 hxfs-save-editor）
├── tests/                   # 开发验证脚本
├── desktop/
│   ├── server.py            # 本地 HTTP API
│   ├── data/                # 工具生成的映射表等
│   ├── static/              # 前端构建产物
│   ├── web/                 # Vue 3 源码
│   └── tools/               # repak、兵种表、自建武将脚本
└── desktop-app/
    ├── src-tauri/           # Tauri 壳
    ├── build.ps1
    └── dist/SUTK修改器/     # 打包输出
```

---

## 常见问题（共用）

- **改了游戏里没变**：必须重新读档，不能只在当前战役里继续玩。
- **游戏正在运行**：多数写入会提示读档后生效；极端情况请先存盘并回主菜单再改。
- **杀毒误报**：本地 Python + 自打包 exe 较常见；工具不联网改游戏文件。

更细的 FAQ 见 [docs/](./docs/) 内各说明。
