import { reactive } from 'vue'
import { api } from './api'
import { STATS } from './constants'

export const store = reactive({
  status: null,
  saves: [],
  current: '',
  saveChecks: {},
  generals: [],
  generalHint: '',
  generalTargets: {},
  externRows: [],
  cities: [],
  cityProblems: [],
  cityFactions: [],
  diplo: [],
  diploHint: '',
  mem: null,
  auditText: '',
  history: [],
  guideHtml: '',
  guideReady: false,
  orphansText: '',
  loading: false,
  scope: 'player',
  force: false,
  setAuto: false,
  setSnap: false,
  caps: {},
  stats: {},
  sections: [],
  moveOfficers: false,
  allowEmpty: false,
  cityTarget: '',
  repairSrc: '',
  memField: 'money',
  memSeed: '',
  memFilter: '',
  memWrite: '999999999',
  uninstallWord: '',
  /** 配置里的自定义路径，空字符串表示用系统默认 */
  savesDir: '',
  externPath: '',
  teamPresets: [],
  teamPresetId: '',
  /** 创建编队页勾选的预设 id */
  selectedTeamPresetIds: [],
  teamsInSave: [],
  /** troopKindId → 中文兵种名（来自游戏 locres） */
  troopKindLabels: {},
})

export function namesOrCurrent() {
  const names = store.saves.filter((s) => store.saveChecks[s.name]).map((s) => s.name)
  if (names.length) return names
  return store.current ? [store.current] : []
}

export function configBody() {
  return {
    sections: [...store.sections],
    caps: { ...store.caps },
    stats: { ...store.stats },
    scope: store.scope,
    auto_apply: store.setAuto,
    snapshot_game: store.setSnap,
  }
}

export function pathConfigBody() {
  return {
    saves_dir: store.savesDir.trim(),
    extern_path: store.externPath.trim(),
  }
}

export async function boot() {
  store.status = await api('/api/status')
  applyStatusCfg()
  await loadTroopKindLabels()
  await loadTeamPresets()
  await loadSaves()
}

export async function loadTroopKindLabels() {
  try {
    const data = await api('/api/troop-kinds')
    store.troopKindLabels = data.kinds || {}
  } catch {
    store.troopKindLabels = {}
  }
}

export function applyStatusCfg() {
  const s = store.status
  if (!s) return
  store.scope = s.cfg.scope === 'all' ? 'all' : 'player'
  store.setAuto = !!s.cfg.auto_apply
  store.setSnap = !!s.cfg.snapshot_game
  store.caps = { ...s.cfg.caps }
  store.stats = { ...s.cfg.stats }
  store.sections = [...s.cfg.sections]
  store.savesDir = s.cfg.saves_dir || ''
  store.externPath = s.cfg.extern_path || ''
}

/** 编队预设以 GET /api/team-presets 为准（会补全内置十支） */
export async function loadTeamPresets() {
  try {
    const data = await api('/api/team-presets')
    store.teamPresets = data.presets || []
    if (!store.teamPresetId && store.teamPresets.length) {
      store.teamPresetId = store.teamPresets[0].id
    }
    const ids = new Set(store.teamPresets.map((p) => p.id))
    store.selectedTeamPresetIds = store.selectedTeamPresetIds.filter((id) => ids.has(id))
  } catch {
    /* 旧后端无接口时保留已有列表 */
  }
}

async function ensureGeneralsForTeams() {
  if (!store.current || store.generals.length) return
  try {
    await loadGenerals()
  } catch {
    /* 仅用于预设表中文名 */
  }
}

export async function loadSaves() {
  const data = await api('/api/saves')
  store.saves = data.saves
  if (store.status) store.status.game_running = data.game_running
  const checks = { ...store.saveChecks }
  data.saves.forEach((s, i) => {
    if (checks[s.name] === undefined) checks[s.name] = i === 0
  })
  store.saveChecks = checks
  if (!store.current && data.saves.length) store.current = data.saves[0].name
  if (store.current && !data.saves.some((s) => s.name === store.current)) {
    store.current = data.saves[0]?.name || ''
  }
}

export async function loadGenerals() {
  if (!store.current) return
  const data = await api('/api/generals?name=' + encodeURIComponent(store.current))
  store.generals = data.generals.map((g) => ({
    ...g,
    edit: { ...g.stats },
  }))
  store.generalTargets = data.targets
  store.generalHint = `${data.name} · ${data.label} · ${data.generals.length} 人。带 ★ 为名录外武将。目标 ${STATS.map((k) => data.targets[k]).join('/')}`
}

export async function loadExtern() {
  const data = await api('/api/extern')
  store.externRows = (data.rows || []).map((r) => ({
    ...r,
    edit: { ...r.stats },
  }))
}

export async function loadCities() {
  if (!store.current) return
  const data = await api('/api/cities?name=' + encodeURIComponent(store.current))
  store.cities = data.cities
  store.cityProblems = data.problems || []
  store.cityFactions = data.factions
  if (!store.cityTarget && data.factions.length) store.cityTarget = data.factions[0].id
}

export async function loadDiplo() {
  if (!store.current) return
  const data = await api('/api/diplo?name=' + encodeURIComponent(store.current))
  store.diplo = data.rows.map((r) => ({
    ...r,
    edit: {
      relation: r.relation ?? null,
      friend: !!r.friend,
      armistice: !!r.armistice,
      favour: num(r.favour),
      favour_other: num(r.favour_other),
    },
  }))
  store.diploHint = `${data.name} · 玩家 ${data.player}（${data.king}）${data.game_running ? ' · 游戏运行中，读档后生效' : ''}`
}

function num(v) {
  if (v === null || v === undefined || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) ? Math.round(n * 1000) / 1000 : null
}

export async function loadAudit() {
  if (!store.current) return
  const data = await api('/api/audit?name=' + encodeURIComponent(store.current))
  const warn = (data.warnings || []).join('\n')
  store.auditText = (data.lines || []).join('\n') + (warn ? '\n' + warn : '')
}

export async function loadHistory() {
  const q = store.current ? '?name=' + encodeURIComponent(store.current) : ''
  const data = await api('/api/history' + q)
  store.history = data.saves
}

export async function loadMem() {
  try {
    store.mem = await api('/api/mem/status')
  } catch (e) {
    store.mem = { error: e.message }
  }
}

export async function loadGuide(renderMarkdown) {
  if (store.guideReady) return
  const data = await api('/api/guide')
  store.guideHtml = renderMarkdown(data.text)
  store.guideReady = true
}

export async function loadOrphans() {
  const data = await api('/api/orphans')
  store.orphansText = data.targets.length ? data.targets.join('\n') : '没有待清理的副本。'
}

export async function loadTeamPresetsPage() {
  await loadTeamPresets()
  await ensureGeneralsForTeams()
}

export async function loadTeamsInSave() {
  if (!store.current) {
    store.teamsInSave = []
    return
  }
  try {
    const data = await api('/api/teams?name=' + encodeURIComponent(store.current))
    store.teamsInSave = data.teams || []
  } catch {
    store.teamsInSave = []
  }
}

export async function loadTeamDeployPage() {
  await loadTeamPresets()
  await loadCities()
  await ensureGeneralsForTeams()
}

export async function loadTeamTroopsPage() {
  await loadTeamsInSave()
}

export async function refreshPage(key) {
  if (key === 'generals') await loadGenerals()
  if (key === 'cities') await loadCities()
  if (key === 'teamPresets') await loadTeamPresetsPage()
  if (key === 'teamDeploy') await loadTeamDeployPage()
  if (key === 'teamTroops') await loadTeamTroopsPage()
  if (key === 'diplo') await loadDiplo()
  if (key === 'check') {
    await loadAudit()
    await loadHistory()
  }
  if (key === 'memory') await loadMem()
  if (key === 'settings') await loadOrphans()
}
