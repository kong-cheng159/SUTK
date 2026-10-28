<script setup>
import { ref, computed, watch, h } from 'vue'
import { NButton, NTag, NText, useMessage } from 'naive-ui'
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

const message = useMessage()
const search = ref('')
const teamFilter = ref('')
const onlyInSave = ref(false)
const onlyInPreset = ref(false)

const tableBodyRef = ref(null)
const tableMaxHeight = useTableMaxHeight(tableBodyRef)
const pagination = useTablePagination(30)
const tableSort = useTableSort(pagination)

watch([search, teamFilter, onlyInSave, onlyInPreset], () => resetPaginationPage(pagination))
watch(
  () => store.customGenerals.length,
  () => resetPaginationPage(pagination),
)

const teamOptions = computed(() => {
  const groups = store.customGeneralsMeta.team_groups || {}
  const keys = Object.keys(groups).sort()
  return [{ label: '全部编组字', value: '' }].concat(
    keys.map((k) => ({ label: `${k}（${groups[k]}人）`, value: k })),
  )
})

const hint = computed(() => {
  const m = store.customGeneralsMeta
  if (m.missing) return '找不到 ExternPersonage.sav，请确认游戏已生成该文件。'
  const parts = [`模板路径：${m.path || '—'}`, `自建 ${m.total ?? store.customGenerals.length} 人`]
  if (m.modify_count) parts.push(`原版改造 ${m.modify_count} 人（见「武将 → 自建模板」）`)
  if (store.current) {
    parts.push(`对照存档：${store.current}`)
  } else {
    parts.push('未选存档：无法显示「是否在档」')
  }
  return parts.join(' · ')
})

const filtered = computed(() => {
  let rows = store.customGenerals
  const tc = teamFilter.value
  if (tc) rows = rows.filter((r) => r.team_char === tc)
  if (onlyInSave.value) rows = rows.filter((r) => r.in_save)
  if (onlyInPreset.value) rows = rows.filter((r) => r.in_preset)
  const q = search.value.trim().toLowerCase()
  if (!q) return rows
  return rows.filter((r) =>
    [r.name, r.surname, r.given, r.guid, r.tactical, ...(r.presets || [])]
      .join(' ')
      .toLowerCase()
      .includes(q),
  )
})

function sortValue(row, key) {
  if (key === 'in_save') {
    if (row.in_save) return 2
    if (row.in_save_file) return 1
    return 0
  }
  if (key === 'in_preset') return row.in_preset ? 1 : 0
  if (key === 'total') {
    const s = row.stats || {}
    return STATS.reduce((n, k) => n + (Number(s[k]) || 0), 0)
  }
  if (STATS.includes(key)) return Number(row.stats?.[key]) || 0
  return row[key] ?? ''
}

const sorted = computed(() => applyTableSort(filtered.value, tableSort.sort, sortValue))
const paged = usePagedRows(sorted, pagination)

async function copyGuid(guid) {
  try {
    await navigator.clipboard.writeText(guid)
    message.success('已复制 GUID')
  } catch {
    message.warning(guid)
  }
}

const scrollX =
  88 + 56 + 56 + 72 + 88 + 96 + 56 + 72 * 6 + 120 + 200 + 48

const columns = computed(() => {
  const cols = [
    {
      title: '姓名',
      key: 'name',
      width: 88,
      fixed: 'left',
      sorter: (a, b) => String(a.name).localeCompare(String(b.name), 'zh'),
      sortOrder: tableSort.sortOrderFor('name'),
    },
    {
      title: '编组',
      key: 'team_char',
      width: 56,
      sorter: (a, b) => sortValue(a, 'team_char').localeCompare(sortValue(b, 'team_char'), 'zh'),
      sortOrder: tableSort.sortOrderFor('team_char'),
      render: (r) =>
        r.team_char
          ? h(NTag, { size: 'small', bordered: false, type: 'info' }, () => r.team_char)
          : '—',
    },
    {
      title: '角色',
      key: 'role_char',
      width: 56,
      render: (r) => r.role_char || '—',
    },
    {
      title: '本国在档',
      key: 'in_save',
      width: 80,
      sorter: (a, b) => sortValue(a, 'in_save') - sortValue(b, 'in_save'),
      sortOrder: tableSort.sortOrderFor('in_save'),
      render: (r) => {
        if (!store.current) return '—'
        if (!r.in_save_file) return h(NText, { depth: 3 }, () => '未入档')
        if (r.save_dead) return h(NTag, { size: 'small', type: 'default' }, () => '已故')
        if (!r.in_save) return h(NTag, { size: 'small', type: 'warning' }, () => '他国')
        return h(NTag, { size: 'small', type: 'success' }, () => r.save_state || '在档')
      },
    },
    {
      title: '预设',
      key: 'in_preset',
      width: 88,
      sorter: (a, b) => sortValue(a, 'in_preset') - sortValue(b, 'in_preset'),
      sortOrder: tableSort.sortOrderFor('in_preset'),
      render: (r) => {
        if (!r.presets?.length) return '—'
        const label = r.presets.length === 1 ? r.presets[0] : `${r.presets.length}条`
        return h(
          NTag,
          { size: 'small', bordered: false, title: r.presets.join('、') },
          () => label,
        )
      },
    },
    {
      title: '战法',
      key: 'tactical',
      width: 96,
      ellipsis: { tooltip: true },
    },
  ]
  for (const k of STATS) {
    cols.push({
      title: STAT_NAME[k],
      key: k,
      width: 56,
      sorter: (a, b) => sortValue(a, k) - sortValue(b, k),
      sortOrder: tableSort.sortOrderFor(k),
      render: (r) => r.stats?.[k] ?? '—',
    })
  }
  cols.push({
    title: 'GUID',
    key: 'guid',
    width: 200,
    ellipsis: { tooltip: true },
    render: (r) =>
      h(
        NButton,
        { size: 'tiny', quaternary: true, onClick: () => copyGuid(r.guid) },
        () => r.guid.slice(0, 8) + '…',
      ),
  })
  return cols
})
</script>

<template>
  <div class="page-fill">
    <p class="hint">
      列出 ExternPersonage.sav 中全部<strong>新建</strong>自建武将。中间「编组字」相同的一般为同一模板队；「本国在档」= 顶部所选存档里、属<strong>玩家势力</strong>的该 GUID 武将（与「存档武将」列表同一规则）。
    </p>
    <n-alert v-if="store.customGeneralsMeta.fallback" type="warning" :bordered="false" style="margin-bottom: 10px">
      当前连上的是<strong>旧版界面服务</strong>（8765 端口未重启），「在档 / 预设」可能不准。请完全退出修改器，在任务管理器结束残留的
      <code>python.exe</code> 后再打开 exe；或覆盖最新的 <code>desktop\server.py</code> 后重开。
    </n-alert>
    <n-alert v-else-if="store.customGeneralsMeta.missing" type="warning" :bordered="false" style="margin-bottom: 10px">
      找不到模板文件，请先运行游戏或检查设置里的路径。
    </n-alert>
    <n-text depth="3" style="display: block; margin-bottom: 10px; font-size: 13px">{{ hint }}</n-text>
    <n-space wrap align="center" style="margin-bottom: 10px">
      <n-input v-model:value="search" clearable placeholder="搜姓名 / GUID / 战法 / 预设" style="width: 240px" />
      <n-select v-model:value="teamFilter" :options="teamOptions" style="width: 140px" />
      <n-checkbox v-model:checked="onlyInSave">仅本国在档</n-checkbox>
      <n-checkbox v-model:checked="onlyInPreset">仅在编队预设</n-checkbox>
      <slot name="actions" />
    </n-space>
    <div class="table-stack">
      <div ref="tableBodyRef" class="table-stack-body">
        <n-data-table
          striped
          size="small"
          :max-height="tableMaxHeight"
          :scroll-x="scrollX"
          :scrollbar-props="{ contentStyle: 'padding-bottom: 12px' }"
          :columns="columns"
          :data="paged"
          :row-key="(r) => r.guid"
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
