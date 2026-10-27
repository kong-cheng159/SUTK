import { appendLog } from './log'

/** 避免未启动后端时首屏 loading 一直不结束 */
const API_TIMEOUT_MS = 12_000

function apiUnreachableMessage(cause) {
  const dev =
    import.meta.env.DEV &&
    ' 浏览器调试需先启动 API：在项目根目录执行 `python\\python.exe desktop\\server.py --port 8765 --no-browser`，再 `npm run dev`。'
  if (cause === 'timeout') {
    return `界面服务没连上（请求超时）。${dev || ' 请用 SUTK修改器.exe 打开，或确认本机 API 已在 8765 端口运行。'}`
  }
  return `界面服务没连上。${dev || ' 如果刚点了提权，等用户账户控制点「是」后再试。'}`
}

export async function api(path, body) {
  const opt = { headers: {} }
  if (body !== undefined) {
    opt.method = 'POST'
    opt.headers['Content-Type'] = 'application/json'
    opt.body = JSON.stringify(body)
  }
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), API_TIMEOUT_MS)
  opt.signal = ctrl.signal
  let res
  try {
    res = await fetch(path, opt)
  } catch (e) {
    const timeout = e?.name === 'AbortError'
    throw new Error(apiUnreachableMessage(timeout ? 'timeout' : 'network'))
  } finally {
    clearTimeout(timer)
  }
  const data = await res.json()
  if (data.lines) appendLog(data.lines)
  if (!data.ok) {
    const err = new Error(data.error || '操作失败')
    err.data = data
    throw err
  }
  return data
}
