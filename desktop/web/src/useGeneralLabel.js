import { computed } from 'vue'
import { store } from './store'

/** 按存档武将名录把 GUID 显示为中文名 */
export function useGeneralLabel() {
  const generalNameByPid = computed(() => {
    const m = new Map()
    for (const g of store.generals) {
      m.set(String(g.pid).toUpperCase(), g.cn || g.pid)
    }
    return m
  })

  function generalLabel(id) {
    if (!id || id === 'None') return '—'
    return generalNameByPid.value.get(String(id).toUpperCase()) || id
  }

  return { generalLabel }
}
