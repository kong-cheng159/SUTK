/** 是否在 Tauri 壳内（非纯浏览器） */
export function isTauri() {
  if (typeof window === 'undefined') return false
  return !!(window.__TAURI_INTERNALS__ || window.__TAURI__)
}

/**
 * @param {string | undefined} defaultPath
 * @returns {Promise<string | null>}
 */
export async function pickSaveFolder(defaultPath) {
  if (!isTauri()) return null
  const { open } = await import('@tauri-apps/plugin-dialog')
  const selected = await open({
    directory: true,
    multiple: false,
    title: '选择存档目录（应包含 .sav 文件，一般为 …\\Saved\\Saves）',
    defaultPath: defaultPath || undefined,
  })
  if (selected == null) return null
  return typeof selected === 'string' ? selected : selected[0] ?? null
}

/**
 * @param {string | undefined} defaultPath
 * @returns {Promise<string | null>}
 */
export async function pickExternSavFile(defaultPath) {
  if (!isTauri()) return null
  const { open } = await import('@tauri-apps/plugin-dialog')
  const selected = await open({
    directory: false,
    multiple: false,
    title: '选择 ExternPersonage.sav',
    defaultPath: defaultPath || undefined,
    filters: [{ name: 'ExternPersonage', extensions: ['sav'] }],
  })
  if (selected == null) return null
  return typeof selected === 'string' ? selected : selected[0] ?? null
}
