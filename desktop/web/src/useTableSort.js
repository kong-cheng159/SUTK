import { ref } from 'vue'
import { resetPaginationPage } from './useTablePagination'

/** 表头排序（配合手动分页：先排序再 slice） */
export function useTableSort(pagination) {
  const sort = ref(null)

  function onSorterUpdate(raw) {
    const s = Array.isArray(raw) ? raw[0] : raw
    if (!s?.columnKey || !s.order || s.order === false) {
      sort.value = null
    } else {
      sort.value = { columnKey: s.columnKey, order: s.order }
    }
    if (pagination) resetPaginationPage(pagination)
  }

  function sortOrderFor(columnKey) {
    if (!sort.value || sort.value.columnKey !== columnKey) return false
    return sort.value.order
  }

  return { sort, onSorterUpdate, sortOrderFor }
}

export function applyTableSort(rows, sort, valueOf) {
  if (!sort.value?.columnKey || !sort.value.order) return rows
  const key = sort.value.columnKey
  const dir = sort.value.order === 'descend' ? -1 : 1
  return [...rows].sort((a, b) => {
    const va = valueOf(a, key)
    const vb = valueOf(b, key)
    if (typeof va === 'number' && typeof vb === 'number') {
      return dir * (va - vb)
    }
    return dir * String(va ?? '').localeCompare(String(vb ?? ''), 'zh-CN', { numeric: true })
  })
}
