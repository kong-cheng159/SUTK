<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import {
  SwapHorizontalOutline,
  PersonOutline,
  ConstructOutline,
  HelpCircleOutline,
  SearchOutline,
} from '@vicons/ionicons5'
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
/** 任命太守等操作时默认只看本国，避免误以为会改他国 */
const playerOnly = ref(true)
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

const playerFid = computed(() => String(store.playerFid || ''))

const filtered = computed(() => {
  let rows = store.cities
  if (playerOnly.value && playerFid.value) {
    const pf = playerFid.value.toLowerCase()
    rows = rows.filter((c) => String(c.fid ?? '').toLowerCase() === pf)
  }
  const q = search.value.trim().toLowerCase()
  if (!q) return rows
  return rows.filter((c) =>
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

const selectedCount = computed(() => checkedKeys.value.length)

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
  <div class="page-fill cities-page">
    <div class="cities-toolbar panel-surface">
      <n-input
        v-model:value="search"
        placeholder="筛选城市或势力"
        clearable
        size="small"
        class="cities-search"
      >
        <template #prefix>
          <n-icon :component="SearchOutline" :size="16" />
        </template>
      </n-input>
      <n-checkbox v-model:checked="playerOnly" size="small">仅我国</n-checkbox>
      <span v-if="selectedCount" class="cities-selection">已选 {{ selectedCount }} 座</span>
      <div class="cities-toolbar-actions">
        <slot name="toolbar" />
      </div>
    </div>

    <section class="cities-ops panel-surface">
      <header class="cities-ops-head">
        <span class="cities-ops-head-title">批量操作</span>
        <span class="cities-ops-head-tip">先在下方表格勾选城市</span>
        <n-popover trigger="click" placement="bottom-end" :width="320">
          <template #trigger>
            <n-button quaternary size="tiny" class="cities-help-btn">
              <template #icon>
                <n-icon :component="HelpCircleOutline" />
              </template>
              说明
            </n-button>
          </template>
          <ul class="cities-help-list hint">
            <li>转移时若未勾选「太守跟着走」，新城往往无太守，可用自动任命填补。</li>
            <li>自动任命<strong>只改玩家势力</strong>的无太守城，他国城市与 AI 太守不会被本工具改动。</li>
            <li>自动任命仅调遣<strong>我国</strong>空闲且偏内政的武将；武统敏过高、已在部队/工作或已有岗位者不会动。</li>
            <li>「修复全吞并」需选对照存档，会先备份当前档。</li>
          </ul>
        </n-popover>
      </header>

      <div class="cities-ops-body">
        <div class="cities-ops-col">
          <div class="cities-ops-col-head">
            <n-icon :component="SwapHorizontalOutline" :size="18" class="cities-ops-icon" />
            <span>转移归属</span>
          </div>
          <n-select
            v-model:value="store.cityTarget"
            :options="factionOptions"
            placeholder="目标势力"
            size="small"
          />
          <div class="cities-checks">
            <n-checkbox v-model:checked="store.moveOfficers" size="small">
              太守和驻守跟着城走
            </n-checkbox>
            <n-checkbox v-model:checked="store.allowEmpty" size="small">
              允许转成零城
            </n-checkbox>
          </div>
          <div class="cities-ops-foot">
            <slot name="transfer" />
          </div>
        </div>

        <div class="cities-ops-col">
          <div class="cities-ops-col-head">
            <n-icon :component="PersonOutline" :size="18" class="cities-ops-icon" />
            <span>任命太守</span>
          </div>
          <p class="cities-ops-note">
            仅<strong>玩家势力</strong>：他国不管。内政型空闲武将；高武统敏保留给出征。
            「任命选中城」= 勾选的本国城；「本国全部无太守」= 我国每一座无太守城（与勾选无关）。
          </p>
          <div class="cities-ops-foot cities-ops-foot--stack">
            <slot name="prefect" />
          </div>
        </div>

        <div class="cities-ops-col cities-ops-col--muted">
          <div class="cities-ops-col-head">
            <n-icon :component="ConstructOutline" :size="18" class="cities-ops-icon" />
            <span>修复对照</span>
          </div>
          <n-select
            v-model:value="store.repairSrc"
            :options="repairOptions"
            placeholder="对照存档"
            size="small"
          />
          <div class="cities-ops-spacer" aria-hidden="true" />
          <div class="cities-ops-foot">
            <slot name="repair" />
          </div>
        </div>
      </div>
    </section>

    <div class="table-stack cities-table panel-surface">
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
.cities-page {
  gap: 10px;
}

.cities-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px 14px;
  padding: 10px 14px;
}

.cities-search {
  width: min(260px, 100%);
  flex: 0 1 auto;
}

.cities-selection {
  font-size: 12px;
  font-weight: 600;
  color: var(--app-accent-deep);
  background: var(--app-accent-soft);
  padding: 4px 10px;
  border-radius: 999px;
  line-height: 1.2;
}

.cities-toolbar-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
  margin-left: auto;
}

.cities-ops {
  overflow: hidden;
}

.cities-ops-head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--app-border, #e2e8f0);
  background: linear-gradient(180deg, #fafbfc 0%, #fff 100%);
}

.cities-ops-head-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--n-text-color-1);
}

.cities-ops-head-tip {
  font-size: 12px;
  color: var(--n-text-color-3);
}

.cities-help-btn {
  margin-left: auto;
}

.cities-help-list {
  margin: 0;
  padding-left: 1.15em;
  font-size: 13px;
}

.cities-help-list li + li {
  margin-top: 8px;
}

.cities-ops-body {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

@media (max-width: 960px) {
  .cities-ops-body {
    grid-template-columns: 1fr;
  }

  .cities-ops-col + .cities-ops-col {
    border-left: none;
    border-top: 1px solid var(--app-border, #e2e8f0);
  }
}

.cities-ops-col {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px 16px 16px;
  min-height: 172px;
}

.cities-ops-col + .cities-ops-col {
  border-left: 1px solid var(--app-border, #e2e8f0);
}

.cities-ops-col-head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--n-text-color-1);
}

.cities-ops-icon {
  color: #0d9488;
  opacity: 0.92;
}

.cities-ops-col--muted .cities-ops-icon {
  color: var(--n-text-color-3);
}

.cities-ops-col--muted .cities-ops-col-head {
  color: var(--n-text-color-2);
}

.cities-ops-spacer {
  flex: 1;
  min-height: 4px;
}

.cities-ops-note {
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--n-text-color-3);
  flex: 1;
}

.cities-checks {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
}

.cities-ops-foot {
  margin-top: auto;
  width: 100%;
}

.cities-ops-foot--stack {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.cities-ops-foot :deep(.n-button),
.cities-ops-foot--stack :deep(.n-button) {
  width: 100%;
}

.cities-table {
  padding: 0;
  overflow: hidden;
}

.cities-table :deep(.n-data-table-wrapper) {
  border: none;
  border-radius: 0;
}

.cities-table :deep(.n-data-table-table) {
  width: 100%;
  table-layout: fixed;
}

.cities-table :deep(.n-data-table-th),
.cities-table :deep(.n-data-table-td) {
  padding-left: 10px;
  padding-right: 10px;
}

.cities-table .table-stack-foot {
  padding: 8px 14px 10px;
  border-top: 1px solid var(--app-border, #e2e8f0);
  background: #fafbfc;
}

</style>
