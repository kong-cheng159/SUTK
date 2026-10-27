import { ref, onMounted, onUnmounted, watch } from 'vue'

/** 表格滚动区底部留白，避免最后一行被 max-height 裁切 */
export const TABLE_BOTTOM_INSET = 48

/** 按表格外层 flex 容器高度设置 max-height（随窗口与布局变化） */
export function useTableMaxHeight(containerRef, min = 160) {
  const maxHeight = ref(400)
  let ro

  function bind(el) {
    ro?.disconnect()
    ro = null
    if (!el) return
    const sync = () => {
      maxHeight.value = Math.max(min, el.clientHeight - TABLE_BOTTOM_INSET)
    }
    sync()
    ro = new ResizeObserver(sync)
    ro.observe(el)
  }

  onMounted(() => {
    bind(containerRef.value)
    watch(
      () => containerRef.value,
      (el) => bind(el),
      { flush: 'post' },
    )
  })

  onUnmounted(() => ro?.disconnect())

  return maxHeight
}
