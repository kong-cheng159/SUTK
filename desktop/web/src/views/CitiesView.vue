<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { store } from '../store'
import { useTableMaxHeight } from '../useTableMaxHeight'
import {
  useTablePagination,
  resetPaginationPage,
  usePagedRows,
  PAGE_SIZE_OPTIONS,
} from '../useTablePagination'
import { useTableSort, applyTableSort } from '../useTableSort'

const search = ref('')
const checkedKeys = ref([])
const pagination = useTablePagination(20)
const tableSort = useTableSort(pagination)

watch(search, () => resetPaginationPage(pagination))
watch(
  () => store.cities.length,
  () => resetPaginationPage(pagination),
)

const tableBodyRef = ref(null)
const tableMaxHeight = useTableMaxHeight(tableBodyRef)
const tableWrapWidth = ref(900)

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return store.cities
  return store.cities.filter((c) =>
    (c.cn + c.key + c.label + c.fid + c.prefect).toLowerCase().includes(q),
  )
})

function citySortValue(row, key) {
  if (key === 'cn') return row.cn || row.key || ''
  if (key === 'capital') return row.capital ? 1 : 0
  if (key === 'level' || key === 'pop') return Number(row[key]) || 0
  return row[key] ?? ''
}

const sortedFiltered = computed(() => applyTableSort(filtered.value, tableSort.sort, citySortValue))
const pagedCities = usePagedRows(sortedFiltered, pagination)

const factionOptions = computed(() =>
  store.cityFactions.map((f) => ({
    label: `${f.label} · ${f.cities}城${f.player ? ' · 玩家' : ''}${f.destroyed ? ' · 已灭' : ''}`,
    value: f.id,
  })),
)

const repairOptions = computed(() => [
  { label: '自动挑选', value: '' },
  ...store.saves.map((s) => ({ label: s.name, value: s.name })),
])

defineExpose({ checkedKeys })

const SELECTION_W = 40
const DATA_COLS = 6

const columns = computed(() => {
  const rest = Math.max(0, tableWrapWidth.value - SELECTION_W)
  const base = Math.max(56, Math.floor(rest / DATA_COLS))
  let used = SELECTION_W + base * DATA_COLS
  const lastExtra = tableWrapWidth.value - used
  const w = (i) => base + (i === DATA_COLS - 1 ? lastExtra : 0)
  return [
    { type: 'selection', width: SELECTION_W },
    {
      title: '城市',
      key: 'cn',
      width: w(0),
      ellipsis: { tooltip: true },
      sorter: (a, b) =>
        String(a.cn || a.key).localeCompare(String(b.cn || b.key), 'zh-CN'),
      sortOrder: tableSort.sortOrderFor('cn'),
      render: (r) => r.cn || r.key,
    },
    {
      title: '归属',
      key: 'label',
      width: w(1),
      ellipsis: { tooltip: true },
      sorter: (a, b) => String(a.label).localeCompare(String(b.label), 'zh-CN'),
      sortOrder: tableSort.sortOrderFor('label'),
    },
    {
      title: '首都',
      key: 'capital',
      width: w(2),
      align: 'center',
      sorter: (a, b) => citySortValue(a, 'capital') - citySortValue(b, 'capital'),
      sortOrder: tableSort.sortOrderFor('capital'),
      render: (r) => (r.capital ? '★' : ''),
    },
    {
      title: '等级',
      key: 'level',
      width: w(3),
      align: 'center',
      sorter: (a, b) => citySortValue(a, 'level') - citySortValue(b, 'level'),
      sortOrder: tableSort.sortOrderFor('level'),
    },
    {
      title: '人口',
      key: 'pop',
      width: w(4),
      align: 'left',
      sorter: (a, b) => citySortValue(a, 'pop') - citySortValue(b, 'pop'),
      sortOrder: tableSort.sortOrderFor('pop'),
    },
    {
      title: '太守',
      key: 'prefect',
      width: w(5),
      align: 'left',
      ellipsis: { tooltip: true },
      sorter: (a, b) => String(a.prefect).localeCompare(String(b.prefect), 'zh-CN'),
      sortOrder: tableSort.sortOrderFor('prefect'),
    },
  ]
})

let ro
onMounted(() => {
  const el = tableBodyRef.value
  if (!el) return
  tableWrapWidth.value = el.clientWidth || 900
  ro = new ResizeObserver(() => {
    tableWrapWidth.value = el.clientWidth || 900
  })
  ro.observe(el)
})

onUnmounted(() => ro?.disconnect())
</script>

<template>
  <div class="page-fill">
    <p class="hint">转移时默认给被转空的势力留一座首都；岗位会清空，任职时间归零。</p>
    <n-space vertical size="small">
      <n-space wrap>
        <n-input v-model:value="search" placeholder="筛选城市或势力" clearable style="width:220px" />
        <slot name="toolbar" />
      </n-space>
      <n-space wrap align="center">
        <n-select v-model:value="store.cityTarget" :options="factionOptions" placeholder="交给势力" style="width:280px" />
        <n-checkbox v-model:checked="store.moveOfficers">太守和驻守跟着城走</n-checkbox>
        <n-checkbox v-model:checked="store.allowEmpty">允许转成零城</n-checkbox>
        <slot name="transfer" />
      </n-space>
      <n-space wrap align="center">
        <n-select v-model:value="store.repairSrc" :options="repairOptions" style="width:220px" />
        <slot name="repair" />
      </n-space>
    </n-space>
    <div class="table-stack cities-table">
      <div ref="tableBodyRef" class="table-stack-body">
        <n-data-table
          striped
          size="small"
          :max-height="tableMaxHeight"
          :scrollbar-props="{ contentStyle: 'padding-bottom: 12px' }"
          :columns="columns"
          :data="pagedCities"
          :row-key="(r) => r.key"
          v-model:checked-row-keys="checkedKeys"
          @update:sorter="tableSort.onSorterUpdate"
        />
      </div>
      <div class="table-stack-foot">
        <n-text depth="3">共 {{ filtered.length }} 条</n-text>
        <n-pagination
          v-model:page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :item-count="filtered.length"
          :page-sizes="PAGE_SIZE_OPTIONS"
          show-size-picker
          show-quick-jumper
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.cities-table :deep(.n-data-table-table) {
  width: 100%;
  table-layout: fixed;
}

.cities-table :deep(.n-data-table-th),
.cities-table :deep(.n-data-table-td) {
  padding-left: 10px;
  padding-right: 10px;
}
</style>
