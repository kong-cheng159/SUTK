官职 mod 工作区（从本机 MainPak 解出，可编辑后重打 pak）

MainPak（只读参考）:
  D:\Program Files (x86)\Steam\steamapps\common\Seres Universalis Three Kingdoms Demo\
  Seres Universalis Three Kingdoms Demo\ProjectA\Content\Paks\pakchunk0-Windows.pak

解包目录（用 FModel / UAssetGUI / Locres 工具改这里面的文件）:
  unpack_out\ProjectA\Content\...

已生成 mod pak（当前内容与官方相同，仅验证打包流程；改完 unpack_out 后请运行 pack.ps1）:
  pakchunk0-Windows_SUTKOfficials_P.pak

安装: 复制上述 .pak 到
  ...\ProjectA\Content\Paks\
  不要改 pakchunk0-Windows.pak。卸载: 删掉 mod pak。

修改器侧同步: desktop\data\officials_mod.json（append_rows 与 DT_Official 新 id 一致）

当前方案（推荐）:
  复用库内 id 4091（破虏将军，8星）→ 修改器与游戏职名均为破虏将军
  不改游戏也可任命且有效果
  若要任免面板多一行：把 4091 加入汉系列表（见 docs\游戏内新增官职操作步骤.md）

逐步操作文档:
  docs\游戏内新增官职操作步骤.md


打包: 在本目录执行
  powershell -ExecutionPolicy Bypass -File pack.ps1
