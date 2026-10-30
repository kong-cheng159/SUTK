import { computed } from 'vue'
import { store } from './store'

function shortGuid(id) {
  const s = String(id)
  return s.length > 12 ? s.slice(0, 8) + '…' : s
}

/** 按存档武将、guid_labels、预设 generals_cn 显示中文名 */
export function useGeneralLabel() {
  const generalNameByPid = computed(() => {
    const m = new Map()
    for (const g of store.generals) {
      if (g.cn) m.set(String(g.pid).toUpperCase(), g.cn)
    }
    for (const [k, v] of Object.entries(store.guidLabels || {})) {
      if (v) m.set(String(k).toUpperCase(), v)
    }
    for (const p of store.teamPresets || []) {
      const gens = p.generals || []
      const cns = p.generals_cn || []
      gens.forEach((gid, i) => {
        const cn = cns[i]
        if (gid && cn) m.set(String(gid).toUpperCase(), cn)
      })
    }
    return m
  })

  function generalLabel(id, cnFallback) {
    if (!id || id === 'None') return '—'
    if (cnFallback) return cnFallback
    const hit = generalNameByPid.value.get(String(id).toUpperCase())
    if (hit) return hit
    return shortGuid(id)
  }

  function generalLabelAt(row, index) {
    const cn = row?.generals_cn?.[index]
    const id = row?.generals?.[index]
    return generalLabel(id, cn)
  }

  return { generalLabel, generalLabelAt }
}
