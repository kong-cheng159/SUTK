import { computed } from 'vue'
import { store } from './store'

/** troopKindId（如 49_2）→ 游戏内兵种中文名 */
export function useTroopKindLabel() {
  const byId = computed(() => store.troopKindLabels || {})

  function troopKindLabel(id) {
    const k = String(id || '').trim()
    if (!k) return '—'
    return byId.value[k] || byId.value[k.split('_')[0]] || k
  }

  function troopKindTitle(id) {
    const k = String(id || '').trim()
    if (!k) return ''
    const cn = byId.value[k] || byId.value[k.split('_')[0]]
    if (cn && cn !== k) return `${cn}（${k}）`
    return k
  }

  return { troopKindLabel, troopKindTitle }
}
