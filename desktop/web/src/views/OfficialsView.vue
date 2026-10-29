<script setup>
import { ref, computed, h, watch, onMounted, onUnmounted } from 'vue'
import { loadOfficials } from '../store'
import { NButton, NInput, NModal, NSelect, NAlert } from 'naive-ui'
import { SearchOutline } from '@vicons/ionicons5'
import { store } from '../store'
import { api } from '../api'
import { useTableMaxHeight } from '../useTableMaxHeight'
import {
  useTablePagination,
  resetPaginationPage,
  usePagedRows,
  PAGE_SIZE_OPTIONS,
} from '../useTablePagination'
import { useTableSort, applyTableSort } from '../useTableSort'

const emit = defineEmits(['done', 'restart-api'])

const backendStale = computed(() => store.status?.features?.officials !== true)

const search = ref('')
const levelFilter = ref('')
const slotFilter = ref('all')
const tableBodyRef = ref(null)
const tableMaxHeight = useTableMaxHeight(tableBodyRef)
const tableWrapWidth = ref(880)

/** 列宽：数值列与操作列固定；职名略宽、任职列限宽，避免右侧大块空白 */
const colLayout = computed(() => {
  const level = 52
  const staffing = 76
  const salary = 52
  const act = 56
  const fixed = level + staffing + salary + act
  const spare = Math.max(180, tableWrapWidth.value - fixed)
  const nameW = Math.min(152, Math.max(108, Math.floor(spare * 0.46)))
  const holderW = Math.min(112, Math.max(88, Math.floor(spare * 0.28)))
  const scrollX = level + nameW + staffing + salary + holderW + act
  return { level, nameW, staffing, salary, holderW, act, scrollX }
})
const pagination = useTablePagination(50)
const tableSort = useTableSort(pagination)
tableSort.sort.value = { columnKey: 'level', order: 'descend' }

const levelOptions = [
  { label: '全部星级', value: '' },
  ...[9, 8, 7, 6, 5, 4, 3, 2, 1].map((n) => ({ label: `${n} 星`, value: n })),
]

watch([search, levelFilter, slotFilter], () => resetPaginationPage(pagination))
watch(
  () => store.officials.length,
  () => resetPaginationPage(pagination),
)

const stats = computed(() => {
  const rows = store.officials
  const appointed = rows.filter((r) => r.holder_cn).length
  return {
    total: rows.length,
    appointed,
    vacant: rows.length - appointed,
  }
})

const filtered = computed(() => {
  let rows = store.officials
  const lv = levelFilter.value
  if (lv !== '' && lv != null) {
    rows = rows.filter((r) => Number(r.level) === Number(lv))
  }
  if (slotFilter.value === 'filled') {
    rows = rows.filter((r) => r.holder_cn)
  } else if (slotFilter.value === 'empty') {
    rows = rows.filter((r) => !r.holder_cn)
  }
  const q = search.value.trim().toLowerCase()
  if (!q) return rows
  return rows.filter((r) =>
    `${r.level}${r.name}${r.game_name || ''}${r.id}${r.holder_cn}${r.staffing}`
      .toLowerCase()
      .includes(q),
  )
})

function sortValue(row, key) {
  if (key === 'level' || key === 'staffing' || key === 'salary') return Number(row[key]) || 0
  if (key === 'id') return Number(row.id) || 0
  if (key === 'holder_cn') return row.holder_cn || ''
  return row[key] ?? ''
}

const sorted = computed(() => {
  const base = applyTableSort(filtered.value, tableSort.sort, sortValue)
  if (tableSort.sort.value?.columnKey) return base
  return [...base].sort((a, b) => {
    const dl = Number(b.level) - Number(a.level)
    if (dl !== 0) return dl
    return Number(b.id) - Number(a.id)
  })
})

const paged = usePagedRows(sorted, pagination)

const showAssign = ref(false)
const assignRow = ref(null)
const assignPid = ref(null)
const assigning = ref(false)

const generalOptions = computed(() => [
  { label: '（空岗）', value: '' },
  ...store.officialsGenerals.map((g) => {
    const extra = g.official_name && g.official !== assignRow.value?.id ? ` · 现${g.official_name}` : ''
    return { label: `${g.cn}${extra}`, value: g.pid }
  }),
])

function setSlotFilter(v) {
  slotFilter.value = v
}

function renderLevel(level) {
  return h('span', { class: 'official-level', 'data-level': String(level) }, `${level}星`)
}

function openAssign(row) {
  assignRow.value = row
  assignPid.value = row.holder_pid || ''
  showAssign.value = true
}

async function submitAssign() {
  if (!assignRow.value || !store.current) return false
  assigning.value = true
  try {
    const data = await api('/api/officials/assign', {
      name: store.current,
      official_id: assignRow.value.id,
      pid: assignPid.value || null,
    })
    emit('done', data.lines?.[0] || '已保存')
    return true
  } catch {
    return false
  } finally {
    assigning.value = false
  }
}

const columns = computed(() => {
  const { level, nameW, staffing, salary, holderW, act } = colLayout.value
  return [
    {
      title: '等级',
      key: 'level',
      width: level,
      align: 'center',
      sorter: (a, b) => a.level - b.level,
      sortOrder: tableSort.sortOrderFor('level'),
      render: (r) => renderLevel(r.level),
    },
    {
      title: '职名',
      key: 'name',
      width: nameW,
      ellipsis: { tooltip: true },
      sorter: (a, b) => String(a.name).localeCompare(String(b.name), 'zh-CN'),
      sortOrder: tableSort.sortOrderFor('name'),
      render: (r) =>
        h('div', { class: 'official-name-cell' }, [
          h('span', { class: 'official-name' }, r.name),
          r.mod ? h('span', { class: 'official-mod-tag' }, '模组') : null,
          h('span', { class: 'official-id' }, `#${r.id}`),
          r.game_name && r.game_name !== r.name
            ? h('span', { class: 'official-game-name' }, `游戏名 ${r.game_name}`)
            : null,
        ]),
    },
    {
      title: '编制',
      key: 'staffing',
      width: staffing,
      align: 'right',
      sorter: (a, b) => a.staffing - b.staffing,
      sortOrder: tableSort.sortOrderFor('staffing'),
      render: (r) => h('span', { class: 'num-cell' }, String(r.staffing)),
    },
    {
      title: '俸禄',
      key: 'salary',
      width: salary,
      align: 'right',
      sorter: (a, b) => a.salary - b.salary,
      sortOrder: tableSort.sortOrderFor('salary'),
      render: (r) => h('span', { class: 'num-cell' }, String(r.salary)),
    },
    {
      title: '任职武将',
      key: 'holder_cn',
      width: holderW,
      ellipsis: { tooltip: true },
      sorter: (a, b) => String(a.holder_cn || '').localeCompare(String(b.holder_cn || ''), 'zh-CN'),
      sortOrder: tableSort.sortOrderFor('holder_cn'),
      render: (r) =>
        h(
          'span',
          { class: r.holder_cn ? 'holder-name' : 'holder-vacant' },
          r.holder_cn || '—',
        ),
    },
    {
      title: '操作',
      key: 'act',
      width: act,
      align: 'center',
      render: (row) =>
        h(
          NButton,
          {
            size: 'tiny',
            quaternary: true,
            type: 'primary',
            onClick: () => openAssign(row),
          },
          { default: () => (row.holder_cn ? '改任' : '任命') },
        ),
    },
  ]
})

function rowClassName(row) {
  return row.holder_cn ? 'row-filled' : 'row-vacant'
}

let tableRo
onMounted(() => {
  if (store.current && !store.officials.length) {
    loadOfficials().catch(() => {})
  }
  const el = tableBodyRef.value
  if (!el) return
  tableWrapWidth.value = el.clientWidth || 880
  tableRo = new ResizeObserver(() => {
    tableWrapWidth.value = el.clientWidth || 880
  })
  tableRo.observe(el)
})

onUnmounted(() => tableRo?.disconnect())
</script>

<template>
  <div class="officials-page page-fill">
    <n-alert v-if="backendStale" type="error" :bordered="false" class="officials-alert">
      当前后端是旧版，没有官职接口。请先点「重启界面服务」，再刷新。
      <template #action>
        <n-button size="small" type="primary" @click="emit('restart-api')">重启界面服务</n-button>
      </template>
    </n-alert>
    <n-alert v-else-if="store.officialsWarning" type="warning" :bordered="false" class="officials-alert">
      {{ store.officialsWarning }}
    </n-alert>

    <header v-if="!backendStale && stats.total" class="officials-head panel-surface">
      <p v-if="store.officialsHint" class="officials-head-line">{{ store.officialsHint }}</p>
      <div class="officials-head-row">
        <div class="officials-chips" role="tablist" aria-label="任职筛选">
          <button
            type="button"
            class="officials-chip"
            :class="{ 'is-active': slotFilter === 'all' && !levelFilter && !search.trim() }"
            @click="setSlotFilter('all')"
          >
            全部 {{ stats.total }}
          </button>
          <button
            type="button"
            class="officials-chip officials-chip--ok"
            :class="{ 'is-active': slotFilter === 'filled' }"
            @click="setSlotFilter('filled')"
          >
            在任 {{ stats.appointed }}
          </button>
          <button
            type="button"
            class="officials-chip officials-chip--muted"
            :class="{ 'is-active': slotFilter === 'empty' }"
            @click="setSlotFilter('empty')"
          >
            空岗 {{ stats.vacant }}
          </button>
          <span class="officials-chip officials-chip--info">
            面板 {{ store.officialsMeta.panel_count || stats.total }} 职
          </span>
          <span
            v-if="(store.officialsMod.append || 0) + (store.officialsMod.override || 0) > 0"
            class="officials-chip officials-chip--mod"
          >
            模组 +{{ (store.officialsMod.append || 0) + (store.officialsMod.override || 0) }}
          </span>
        </div>
        <span v-if="filtered.length !== stats.total" class="officials-filter-hint">
          当前 {{ filtered.length }} 条
        </span>
      </div>
    </header>

    <div class="officials-toolbar panel-surface">
      <n-input
        v-model:value="search"
        size="small"
        clearable
        placeholder="搜职名、游戏原名（破虏）、id（4091）…"
        class="officials-search"
      >
        <template #prefix>
          <n-icon :component="SearchOutline" />
        </template>
      </n-input>
      <n-select
        v-model:value="levelFilter"
        size="small"
        :options="levelOptions"
        class="officials-filter"
        placeholder="星级"
      />
      <div class="officials-toolbar-actions">
        <slot name="toolbar" />
      </div>
    </div>

    <div class="table-stack officials-table panel-surface">
      <div ref="tableBodyRef" class="table-stack-body officials-table-body">
        <n-data-table
          size="small"
          :bordered="false"
          :single-line="false"
          :max-height="tableMaxHeight"
          :scroll-x="colLayout.scrollX"
          :scrollbar-props="{ contentStyle: 'padding-bottom: 8px' }"
          :columns="columns"
          :data="paged"
          :row-key="(r) => r.id"
          :row-class-name="rowClassName"
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

    <n-modal
      v-model:show="showAssign"
      preset="dialog"
      :title="assignRow ? `任免 · ${assignRow.name}` : '任免'"
      positive-text="保存"
      negative-text="取消"
      :loading="assigning"
      @positive-click="() => submitAssign()"
    >
      <p v-if="assignRow" class="modal-meta">
        {{ assignRow.level }}星 · 编制 {{ assignRow.staffing }} · 俸禄 {{ assignRow.salary }} · id
        {{ assignRow.id }}
      </p>
      <n-select
        v-model:value="assignPid"
        filterable
        clearable
        placeholder="选择本国武将，留空则清空该职"
        :options="generalOptions"
      />
    </n-modal>
  </div>
</template>

<style scoped>
.officials-page {
  gap: 10px;
}

.officials-alert {
  margin-bottom: 0;
}

.officials-head {
  padding: 10px 14px 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.officials-head-line {
  margin: 0;
  font-size: 13px;
  color: var(--app-ink-muted);
  line-height: 1.45;
}

.officials-head-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px 14px;
}

.officials-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.officials-chip {
  font-size: 12px;
  font-weight: 600;
  line-height: 1.2;
  padding: 5px 12px;
  border-radius: 999px;
  border: 1px solid transparent;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
  background: var(--app-accent-soft);
  color: var(--app-accent-deep);
}

.officials-chip:hover {
  border-color: var(--app-accent-ring);
}

.officials-chip.is-active {
  background: var(--app-accent);
  color: #fff;
  border-color: var(--app-accent);
}

.officials-chip--ok {
  background: rgba(24, 160, 88, 0.1);
  color: #15803d;
}

.officials-chip--ok.is-active {
  background: #18a058;
  color: #fff;
  border-color: #18a058;
}

.officials-chip--muted {
  background: var(--app-surface-muted);
  color: var(--app-ink-muted);
  font-weight: 500;
}

.officials-chip--muted.is-active {
  background: #64748b;
  color: #fff;
  border-color: #64748b;
}

.officials-chip--info {
  cursor: default;
  background: var(--app-surface-muted);
  color: var(--app-ink-muted);
  font-weight: 500;
}

.officials-chip--mod {
  background: rgba(234, 88, 12, 0.12);
  color: #c2410c;
  font-weight: 600;
  cursor: default;
}

:deep(.official-mod-tag) {
  flex-shrink: 0;
  font-size: 10px;
  font-weight: 600;
  padding: 0 5px;
  border-radius: 4px;
  background: rgba(234, 88, 12, 0.15);
  color: #c2410c;
}

:deep(.official-game-name) {
  display: block;
  width: 100%;
  font-size: 11px;
  color: var(--app-ink-muted);
  font-weight: 400;
}

.officials-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px 12px;
  padding: 8px 14px;
}

.officials-search {
  width: min(260px, 100%);
  flex: 0 1 auto;
}

.officials-filter {
  width: 108px;
  flex: 0 0 auto;
}

.officials-filter-hint {
  font-size: 12px;
  color: var(--n-text-color-3);
  margin-left: auto;
}

.officials-toolbar-actions {
  margin-left: auto;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.officials-table-body :deep(.n-data-table-wrapper) {
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
}

.officials-table-body :deep(.n-data-table-table) {
  table-layout: fixed;
}

.officials-table-body :deep(.n-data-table-base-table) {
  width: max-content;
  max-width: 100%;
}

:deep(.official-level) {
  display: inline-block;
  min-width: 40px;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  line-height: 1.35;
  font-variant-numeric: tabular-nums;
  background: var(--app-surface-muted);
  color: var(--app-ink-muted);
}

:deep(.official-level[data-level='9']),
:deep(.official-level[data-level='8']) {
  background: rgba(13, 148, 136, 0.14);
  color: var(--app-accent-deep);
}

:deep(.official-level[data-level='7']),
:deep(.official-level[data-level='6']) {
  background: rgba(59, 130, 246, 0.1);
  color: #1d4ed8;
}

:deep(.official-name-cell) {
  display: flex;
  align-items: baseline;
  gap: 6px;
  min-width: 0;
}

:deep(.official-name) {
  font-weight: 500;
  color: var(--app-ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

:deep(.official-id) {
  font-size: 11px;
  flex-shrink: 0;
  color: var(--app-ink-muted);
  font-variant-numeric: tabular-nums;
}

:deep(.num-cell) {
  font-variant-numeric: tabular-nums;
  font-size: 13px;
}

:deep(.holder-name) {
  font-size: 13px;
}

:deep(.holder-vacant) {
  color: var(--app-ink-muted);
  font-size: 12px;
}

:deep(.row-vacant td:first-child) {
  box-shadow: inset 3px 0 0 rgba(100, 116, 139, 0.35);
}

:deep(.row-filled td:first-child) {
  box-shadow: inset 3px 0 0 var(--app-accent);
}

.modal-meta {
  margin: 0 0 12px;
  font-size: 12px;
  color: var(--n-text-color-3);
  line-height: 1.5;
}
</style>
