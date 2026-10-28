<script setup>
import { ref, computed, h, watch } from 'vue'
import { NInputNumber, NButton, NInput, NSelect, NCheckbox, NSpace } from 'naive-ui'
import { store } from '../store'
import { STATS, STAT_NAME } from '../constants'
import { useTableMaxHeight } from '../useTableMaxHeight'
import {
  useTablePagination,
  resetPaginationPage,
  usePagedRows,
  PAGE_SIZE_OPTIONS,
} from '../useTablePagination'
import { useTableSort, applyTableSort } from '../useTableSort'

/** 列宽之和 + 竖滚动条占位，避免最后一列被挡住 */
const SCROLLBAR_GUTTER = 18
const saveTableScrollX = 40 + 100 + 72 * 6 + 64 + 84 + SCROLLBAR_GUTTER
const externTableScrollX = 64 + 92 + 72 * 6 + 64 + 84 + SCROLLBAR_GUTTER
const saveTableBodyRef = ref(null)
const externTableBodyRef = ref(null)
const saveTableMaxHeight = useTableMaxHeight(saveTableBodyRef)
const externTableMaxHeight = useTableMaxHeight(externTableBodyRef)

const savePagination = useTablePagination(20)
const externPagination = useTablePagination(20)
const saveSort = useTableSort(savePagination)
const externSort = useTableSort(externPagination)

const emit = defineEmits(['write-one', 'write-extern', 'reload-extern', 'clone-extern'])
const tab = ref('save')
const search = ref('')
const cloneSurname = ref('')
const cloneName = ref('')
const cloneSource = ref('6CD5900E4F37C42335D7F981B59DA06D')
const cloneAddSave = ref(true)

const externSourceOptions = computed(() =>
  (store.externRows || [])
    .filter((r) => r.kind === 'new')
    .map((r) => ({ label: `${r.name} · ${String(r.guid).slice(0, 8)}…`, value: r.guid })),
)

watch(
  () => externSourceOptions.value.length,
  (n) => {
    if (n && !externSourceOptions.value.some((o) => o.value === cloneSource.value)) {
      cloneSource.value = externSourceOptions.value[0].value
    }
  },
  { immediate: true },
)

function submitClone() {
  if (!cloneSurname.value.trim() && !cloneName.value.trim()) return
  emit('clone-extern', {
    source_guid: cloneSource.value,
    surname: cloneSurname.value.trim(),
    name: cloneName.value.trim(),
    add_to_save: cloneAddSave.value,
  })
}

watch(search, () => resetPaginationPage(savePagination))
watch(
  () => store.generals.length,
  () => resetPaginationPage(savePagination),
)
watch(
  () => store.externRows.length,
  () => resetPaginationPage(externPagination),
)

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return store.generals
  return store.generals.filter(
    (g) =>
      String(g.pid).toLowerCase().includes(q) ||
      (g.cn || '').toLowerCase().includes(q),
  )
})

function saveSortValue(row, key) {
  if (key === 'cn') return row.cn || row.pid || ''
  if (key === 'custom') return row.custom ? 1 : 0
  if (key === 'total') return Number(row.total) || 0
  if (STATS.includes(key)) return Number(row.edit?.[key] ?? row.stats?.[key]) || 0
  return row[key]
}

function externSortValue(row, key) {
  if (key === 'kind') return row.kind === 'new' ? 0 : 1
  if (key === 'name') return row.name || ''
  if (key === 'tactical') return row.tactical ?? ''
  if (STATS.includes(key)) return Number(row.edit?.[key] ?? row.stats?.[key]) || 0
  return row[key]
}

const sortedFiltered = computed(() => applyTableSort(filtered.value, saveSort.sort, saveSortValue))
const pagedSave = usePagedRows(sortedFiltered, savePagination)
const externAll = computed(() => store.externRows)
const sortedExtern = computed(() => applyTableSort(externAll.value, externSort.sort, externSortValue))
const pagedExtern = usePagedRows(sortedExtern, externPagination)

const saveColumns = computed(() => {
  const cols = [
    {
      title: '',
      key: 'custom',
      width: 40,
      sorter: (a, b) => saveSortValue(a, 'custom') - saveSortValue(b, 'custom'),
      sortOrder: saveSort.sortOrderFor('custom'),
      render: (r) => (r.custom ? '★' : ''),
    },
    {
      title: '武将',
      key: 'cn',
      width: 100,
      ellipsis: { tooltip: true },
      sorter: (a, b) =>
        String(a.cn || a.pid).localeCompare(String(b.cn || b.pid), 'zh-CN'),
      sortOrder: saveSort.sortOrderFor('cn'),
      render: (r) => r.cn || r.pid,
    },
  ]
  STATS.forEach((k) => {
    cols.push({
      title: STAT_NAME[k],
      key: k,
      width: 72,
      sorter: (a, b) => saveSortValue(a, k) - saveSortValue(b, k),
      sortOrder: saveSort.sortOrderFor(k),
      render(row) {
        return h(NInputNumber, {
          size: 'small',
          showButton: false,
          value: row.edit[k],
          onUpdateValue: (v) => {
            row.edit[k] = v
          },
        })
      },
    })
  })
  cols.push({
    title: '合计',
    key: 'total',
    width: 64,
    sorter: (a, b) => saveSortValue(a, 'total') - saveSortValue(b, 'total'),
    sortOrder: saveSort.sortOrderFor('total'),
  })
  cols.push({
    title: '',
    key: 'act',
    width: 84,
    fixed: 'right',
    render: (row) =>
      h(
        NButton,
        { size: 'tiny', type: 'primary', onClick: () => emit('write-one', row) },
        { default: () => '写入' },
      ),
  })
  return cols
})

const externColumns = computed(() => {
  const cols = [
    {
      title: '类型',
      key: 'kind',
      width: 64,
      sorter: (a, b) => externSortValue(a, 'kind') - externSortValue(b, 'kind'),
      sortOrder: externSort.sortOrderFor('kind'),
      render: (r) => (r.kind === 'new' ? '自建' : '改造'),
    },
    {
      title: '姓名',
      key: 'name',
      width: 92,
      ellipsis: { tooltip: true },
      sorter: (a, b) =>
        String(a.name).localeCompare(String(b.name), 'zh-CN'),
      sortOrder: externSort.sortOrderFor('name'),
    },
  ]
  STATS.forEach((k) => {
    cols.push({
      title: STAT_NAME[k],
      key: k,
      width: 72,
      sorter: (a, b) => externSortValue(a, k) - externSortValue(b, k),
      sortOrder: externSort.sortOrderFor(k),
      render(row) {
        return h(NInputNumber, {
          size: 'small',
          showButton: false,
          value: row.edit[k],
          onUpdateValue: (v) => {
            row.edit[k] = v
          },
        })
      },
    })
  })
  cols.push({
    title: '战法',
    key: 'tactical',
    width: 64,
    sorter: (a, b) =>
      String(a.tactical ?? '').localeCompare(String(b.tactical ?? ''), 'zh-CN'),
    sortOrder: externSort.sortOrderFor('tactical'),
  })
  cols.push({
    title: '',
    key: 'act',
    width: 84,
    fixed: 'right',
    render: (row) =>
      h(
        NButton,
        { size: 'tiny', type: 'primary', onClick: () => emit('write-extern', row) },
        { default: () => '写入' },
      ),
  })
  return cols
})
</script>

<template>
  <div class="page-fill">
    <n-tabs v-model:value="tab" type="segment" style="width:fit-content" @update:value="(v) => v === 'extern' && $emit('reload-extern')">
      <n-tab-pane name="save" tab="存档武将" />
      <n-tab-pane name="extern" tab="自建模板" />
    </n-tabs>
    <template v-if="tab === 'save'">
      <p class="hint">{{ store.generalHint }}</p>
      <n-space>
        <n-input v-model:value="search" placeholder="筛选武将名" clearable style="width:220px" />
        <slot name="save-actions" />
      </n-space>
      <div class="table-stack">
        <div ref="saveTableBodyRef" class="table-stack-body">
          <n-data-table
            striped
            size="small"
            :max-height="saveTableMaxHeight"
            :scroll-x="saveTableScrollX"
            :scrollbar-props="{ contentStyle: 'padding-bottom: 12px' }"
            :columns="saveColumns"
            :data="pagedSave"
            :row-key="(r) => r.pid"
            @update:sorter="saveSort.onSorterUpdate"
          />
        </div>
        <div class="table-stack-foot">
          <n-text depth="3">共 {{ filtered.length }} 条</n-text>
          <n-pagination
            v-model:page="savePagination.page"
            v-model:page-size="savePagination.pageSize"
            :item-count="filtered.length"
            :page-sizes="PAGE_SIZE_OPTIONS"
            show-size-picker
            show-quick-jumper
          />
        </div>
      </div>
    </template>
    <template v-else>
      <p class="hint">
        模板在 ExternPersonage.sav：新开战役会带上。完整列表见侧栏「自建名录」。下方「克隆新建」可复制一名现有自建（如霍骠垒）改姓名为新人。
      </p>
      <n-space align="center" wrap style="margin-bottom: 10px">
        <n-select
          v-model:value="cloneSource"
          :options="externSourceOptions"
          placeholder="复制自"
          size="small"
          style="width: 220px"
        />
        <n-input v-model:value="cloneSurname" size="small" placeholder="姓" style="width: 72px" />
        <n-input v-model:value="cloneName" size="small" placeholder="名" style="width: 96px" />
        <n-checkbox v-model:checked="cloneAddSave" size="small">同时加入当前存档</n-checkbox>
        <n-button
          type="primary"
          size="small"
          :disabled="!cloneSurname.trim() && !cloneName.trim()"
          @click="submitClone"
        >
          克隆新建
        </n-button>
      </n-space>
      <div class="table-stack">
        <div ref="externTableBodyRef" class="table-stack-body">
          <n-data-table
            striped
            size="small"
            :max-height="externTableMaxHeight"
            :scroll-x="externTableScrollX"
            :scrollbar-props="{ contentStyle: 'padding-bottom: 12px' }"
            :columns="externColumns"
            :data="pagedExtern"
            :row-key="(r) => r.guid"
            @update:sorter="externSort.onSorterUpdate"
          />
        </div>
        <div class="table-stack-foot">
          <n-text depth="3">共 {{ externAll.length }} 条</n-text>
          <n-pagination
            v-model:page="externPagination.page"
            v-model:page-size="externPagination.pageSize"
            :item-count="externAll.length"
            :page-sizes="PAGE_SIZE_OPTIONS"
            show-size-picker
          />
        </div>
      </div>
    </template>
  </div>
</template>
