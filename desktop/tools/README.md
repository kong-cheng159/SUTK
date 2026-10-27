# desktop/tools

开发用工具，**默认不会**打进 `dist\SUTK修改器` 便携包。

| 文件 | 说明 |
|------|------|
| `repak.exe` | 从 UE pak 读取单个文件（需 Oodle） |
| `oo2core_9_win64.dll` | Oodle 解压库，放在本目录并设 `OO2PATH` 指向此处 |
| `build_troop_kinds.py` | 从 `Game.locres` 或 pak 生成 `../troop_kinds_zh.json` |
| `Game.zh-CN.locres` | 可选缓存（体积大，建议本地保留、勿提交 git） |
| `u4pak.py` | 经典 pak 脚本，**不适用于**本游戏 V11+Oodle |

## 更新兵种中文表

```powershell
$env:OO2PATH = "本目录绝对路径"
..\..\python\python.exe build_troop_kinds.py "D:\Steam\...\pakchunk0-Windows.pak"
```

成功后覆盖 `desktop\troop_kinds_zh.json`，再打包或复制到 dist 的 `desktop\`。

详见 **desktop-app/打包说明.md** 第 7 节。
