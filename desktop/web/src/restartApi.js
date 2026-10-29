import { isTauri } from './tauriPick'
import { api } from './api'

/** 结束 8765 旧进程并拉起新版 desktop/server.py（Tauri 内优先走原生命令） */
export async function restartApiServer() {
  if (isTauri()) {
    try {
      const { invoke } = await import('@tauri-apps/api/core')
      await invoke('restart_api')
      return
    } catch (e) {
      const msg = e?.message || String(e)
      if (/restart_api|not found|Unknown command/i.test(msg)) {
        throw new Error(
          '当前 exe 还不支持一键重启。请先完全退出修改器，双击目录里的「重启后端.bat」，再重新打开修改器。',
        )
      }
      throw e
    }
  }
  try {
    await api('/api/server/restart', {})
    await new Promise((r) => setTimeout(r, 800))
  } catch (e) {
    if (e.message?.includes('没有这个接口')) {
      throw new Error(
        '当前后端太旧，无法自助重启。请完全退出修改器后双击「重启后端.bat」，或运行 desktop\\重启后端.ps1。',
      )
    }
    throw e
  }
}

export async function statusHasOfficials() {
  try {
    const data = await api('/api/status')
    return data?.features?.officials === true
  } catch {
    return false
  }
}
