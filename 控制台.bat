@echo off
chcp 936 >nul
setlocal
set "L=%~dp0launcher.cmd"
set "J=%~dp0经验总结.md"
if not exist "%L%" (
  echo [错误] 找不到 launcher.cmd，请重新解压安装。
  pause & exit /b 1
)

:menu
cls
echo ==================================================
echo    SUTK 修改器 · 控制台
echo ==================================================
call "%L%" --report
echo.
echo   ---- 应用（改哪份存档都会先让你选）----
echo   [1] 应用修改（按当前已勾模块执行）
echo   [2] 选择要改的模块
echo   [3] 自定义目标数值（金钱/兵力/粮食/科技/六维）
echo   [4] 一键还原（危险：把所有修改还原成备份）
echo.
echo   ---- 快捷（只改一项，同样先选存档）----
echo   [5] 只满科技
echo   [6] 只满金钱
echo   [7] 只满兵役 + 粮食
echo   [8] 只补满兵力（全兵种）
echo.
echo   [G] 武将六维（批量 / 单个 / 自建模板）
echo   [M] 城市操控（转移 / 修复 / 回滚 / 历史版本）
echo.
echo   ---- 工具 ----
echo   [V] 存档体检（改完必跑：结构校验 + 原版基线对比）
echo   [A] 自动修改开关 / 备份清理
echo   [B] 内存定位（CE 式，改当前游戏内存）
echo   [C] 外交（关系 / 人情 / 同盟 / 停战）
echo   [E] 经验总结（防坑指南，改档前看一眼）
echo.
echo   [D] 安全卸载
echo   [0] 退出
echo.
set "C="
set /p "C=请输入编号回车: "
if not defined C (
  echo.
  echo   [i] 没有输入编号，退出。
  exit /b 0
)

if /i "%C%"=="1" goto p_apply
if /i "%C%"=="2" goto p_pick
if /i "%C%"=="3" goto p_custom
if /i "%C%"=="4" goto p_restore
if /i "%C%"=="5" goto p_tech
if /i "%C%"=="6" goto p_money
if /i "%C%"=="7" goto p_con_food
if /i "%C%"=="8" goto p_troop
if /i "%C%"=="G" goto p_general
if /i "%C%"=="B" goto p_mem
if /i "%C%"=="C" goto p_diplo
if /i "%C%"=="D" goto p_uninstall
if /i "%C%"=="M" goto p_city
if /i "%C%"=="V" goto p_audit
if /i "%C%"=="A" goto p_auto
if /i "%C%"=="E" goto p_exp
if "%C%"=="0" exit /b 0
goto menu

:p_apply
call "%L%" --pick-save
echo.
pause & goto menu

:p_pick
call "%L%" --pick
echo.
pause & goto menu

:p_custom
call "%L%" --custom
echo.
pause & goto menu

:p_restore
call "%L%" --pick-save --restore
echo.
pause & goto menu

:p_tech
call "%L%" --sections tech --pick-save
echo.
pause & goto menu

:p_money
call "%L%" --sections money --pick-save
echo.
pause & goto menu

:p_con_food
call "%L%" --sections conscript,food --pick-save
echo.
pause & goto menu

:p_troop
call "%L%" --sections troop --pick-save
echo.
pause & goto menu

:p_exp
cls
echo ==================================================
echo    经验总结 / 防坑指南
echo ==================================================
echo.
if not exist "%J%" (
  echo   [i] 没找到 经验总结.md，请重新解压安装包。
) else (
  type "%J%"
)
echo.
pause & goto menu

:p_general
cls
echo ==================================================
echo    武将六维  统率 / 武力 / 敏捷 / 智力 / 政治 / 魅力
echo ==================================================
echo.
echo   [1] 批量：先设六维目标值，然后选存档应用
echo   [2] 单个：列出势力武将，逐个点名修改
echo   [3] 自建武将模板（ExternPersonage.sav，只影响以后新开战局）
echo   [0] 返回
echo.
set "S="
set /p "S=请选择: "
if not defined S goto menu
if "%S%"=="1" goto g_batch
if "%S%"=="2" goto g_single
if "%S%"=="3" goto g_extern
goto menu

:g_extern
echo.
echo  改的是编辑器里的自建武将模板（即"新建/还原武将"）。
echo  保存之后只对以后新开战局生效，已有存档不受影响。
echo.
call "%L%" --edit-extern
echo.
pause & goto menu

:g_batch
echo.
call "%L%" --custom-stats
echo.
echo  接着选择要应用的一份或多份存档...
call "%L%" --sections attr --pick-save
echo.
pause & goto menu

:g_single
echo.
echo  改的是"游戏存档"里那份存档。
echo.
call "%L%" --edit-general
echo.
pause & goto menu

:p_auto
echo.
call "%L%" --report
echo.
echo   [1] 关闭自动修改（推荐；游戏保存时不碰任何存档）
echo   [2] 开启自动修改（游戏保存时自动刷所有存档，慎用）
echo   [3] 游戏自动存档时，本地是否留快照（默认关，省空间）
echo   [4] 清理：把游戏内已删除的存档的备份回收
echo   [0] 返回
echo.
set "S="
set /p "S=  选择: "
if not defined S goto menu
if "%S%"=="1" call "%L%" --set-auto off
if "%S%"=="2" call "%L%" --set-auto on
if "%S%"=="3" goto a_snap
if "%S%"=="4" call "%L%" --cleanup
echo.
pause & goto menu

:a_snap
echo.
echo   [1] 关（默认）：只有工具改档前才留快照，游戏自动存档不留
echo   [2] 开：每次游戏存档都在本地留一份（占空间但最保险）
echo   [0] 返回
echo.
set "T="
set /p "T=  选择: "
if not defined T goto menu
if "%T%"=="1" call "%L%" --set-snap off
if "%T%"=="2" call "%L%" --set-snap on
echo.
pause & goto menu

:p_audit
cls
echo ==================================================
echo    存档体检  结构不变量 + 原版基线对比
echo ==================================================
echo.
call "%L%" --audit
echo.
pause & goto menu

:p_city
echo.
echo   ------------------------------ 城市操控 ------------------------------
echo    [1] 查看所有城市（势力归属一览表）
echo    [2] 转移城市（先选城市，再选给哪个势力）
echo    [3] 只留一座城给自己
echo    [4] 修复"全吞并"卡崩（势力没城后自动留一座）
echo    [5] 存档健康检查（有没有会导致崩溃的悬空状态）
echo    [6] 回滚 / 撤销（先选存档 -> 选版本，恢复到之前某一次）
echo    [7] 看看有哪些历史版本（只查看，不改东西）
echo    [0] 返回
echo.
set "S="
set /p "S=  选择: "
if not defined S goto menu
if "%S%"=="1" goto c_list
if "%S%"=="2" goto c_move
if "%S%"=="3" goto c_check
if "%S%"=="4" goto c_repair
if "%S%"=="5" goto c_health
if "%S%"=="6" goto c_undo
if "%S%"=="7" goto c_hist
goto menu

:c_hist
echo.
call "%L%" --history
echo.
pause & goto p_city

:c_health
echo.
call "%L%" --health
echo.
pause & goto p_city

:c_undo
echo.
echo  回滚当前的所有改动都在 history 里，随时可以滚回去。
echo.
call "%L%" --undo-transfer
echo.
pause & goto p_city

:c_repair
echo.
echo  某势力的城被全部拿走后，游戏会因为"势力还在但没城"而崩溃。
echo  本功能自动给每个还存活的势力留一座城，并把太重恢复回去。
echo.
call "%L%" --repair-annex
echo.
pause & goto p_city

:c_list
echo.
call "%L%" --cities
echo.
pause & goto p_city

:c_check
echo.
call "%L%" --check-map
echo.
pause & goto p_city

:c_move
echo.
call "%L%" --transfer
echo.
pause & goto p_city

:p_mem
call "%L%" --memscan --wizard
echo.
pause & goto menu

:p_diplo
call "%L%" --diplo
echo.
pause & goto menu

:p_uninstall
call "%L%" --uninstall
echo.
pause & exit /b 0
