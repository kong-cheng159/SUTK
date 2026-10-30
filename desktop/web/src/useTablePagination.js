import { reactive, computed } from 'vue'

export function useTablePagination(pageSize = 20) {
  return reactive({
    page: 1,
    pageSize,
  })
}

export function resetPaginationPage(pagination) {
  pagination.page = 1
}

export const PAGE_SIZE_OPTIONS = [10, 20, 30, 50, 100, 200]

/** 前端分页切片 */
export function usePagedRows(sourceRef, pagination) {
  return computed(() => {
    const arr = sourceRef.value ?? []
    const start = (pagination.page - 1) * pagination.pageSize
    return arr.slice(start, start + pagination.pageSize)
  })
}
