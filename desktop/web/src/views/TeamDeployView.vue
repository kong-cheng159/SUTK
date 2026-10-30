<script setup>
import { computed, h, ref, watch } from 'vue'
import { useMessage, useDialog } from 'naive-ui'
import { store, loadTeamsInSave } from '../store'
import { api } from '../api'
import { appendLog } from '../log'
import { useGeneralLabel } from '../useGeneralLabel'
import { useTroopKindLabel } from '../useTroopKindLabel'
import { useTableMaxHeight } from '../useTableMaxHeight'
import {
  useTablePagination,
  resetPaginationPage,
  usePagedRows,
  PAGE_SIZE_OPTIONS,
} from '../useTablePagination'

const message = useMessage()
const dialog = useDialog()
const { generalLabelAt } = useGeneralLabel()
const { troopKindLabel, troopKindTitle } = useTroopKindLabel()

const tableBodyRef = ref(null)
const tableMaxHeight = useTableMaxHeight(tableBodyRef, 240)
const pagination = useTablePagination(20)
const paged = usePagedRows(computed(() => store.teamPresets), pagination)

watch(
  () => store.teamPresets.length,
  () => resetPaginationPage(pagination),
)

const deployCityKey = ref('')

const playerFid = computed(() => String(store.playerFid || ''))

const playerCityOptions = computed(() => {
  const pf = playerFid.value.toLowerCase()
  if (!pf) return []
  return store.cities
    .filter((c) => String(c.fid ?? '').toLowerCase() === pf)
    .map((c) => ({
      label: `${c.cn || c.key}${c.capital ? ' ★' : ''}`,
      value: c.key,
    }))
})

const citySelectPlaceholder = computed(() => {
  if (!store.current) return '请先在侧栏选择存档'
  if (!playerFid.value) return '正在加载城市…'
  if (!playerCityOptions.value.length) return '我国暂无城市（或存档无玩家势力）'
  return '选择我国已占城市'
})

watch(
  () => [store.current, playerCityOptions.value.length],
  () => {
    if (!deployCityKey.value && playerCityOptions.value.length) {
      deployCityKey.value = playerCityOptions.value[0].value
    }
    if (
      deployCityKey.value &&
      !playerCityOptions.value.some((o) => o.value === deployCityKey.value)
    ) {
      deployCityKey.value = playerCityOptions.value[0]?.value || ''
    }
  },
  { immediate: true },
)

const checkedPresetKeys = computed({
  get: () => store.selectedTeamPresetIds.map(String),
  set: (keys) => {
    store.selectedTeamPresetIds = keys.map(String)
  },
})

function selectAllPresets() {
  store.selectedTeamPresetIds = store.teamPresets.map((p) => String(p.id))
  message.info(`已勾选 ${store.selectedTeamPresetIds.length} 条预设`)
}

function clearSelection() {
  store.selectedTeamPresetIds = []
}

function deploy() {
  if (!store.current) {
    message.warning('请先选择存档')
    return
  }
  if (!store.selectedTeamPresetIds.length) {
    message.warning('请勾选要创建的编队预设')
    return
  }
  if (!deployCityKey.value) {
    message.warning('请选择目标城市')
    return
  }
  const city = store.cities.find((c) => c.key === deployCityKey.value)
  const cityLabel = city?.cn || deployCityKey.value
  const n = store.selectedTeamPresetIds.length
  dialog.warning({
    title: '创建三人编队',
    content:
      `在「${cityLabel}」创建 ${n} 支部队？\n` +
      '每支 = 主将 + 2 副将；武将须空闲且不在其他队。\n' +
      '兵种列标注「·唯一」或「·限N」表示本势力可创建支数；全选二十支时若超出上限会自动跳过并写日志。',
    positiveText: '创建',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const data = await api('/api/teams/deploy', {
          name: store.current,
          city_key: deployCityKey.value,
          preset_ids: store.selectedTeamPresetIds,
        })
        appendLog((data.lines || []).join('\n'))
        message.success('已写入存档，可在「存档部队」查看')
        await loadTeamsInSave()
        return true
      } catch (e) {
        message.error(e.message || '创建失败')
        appendLog(e.message)
        return false
      }
    },
  })
}

const selectedPresets = computed(() => {
  const ids = new Set(store.selectedTeamPresetIds.map(String))
  return store.teamPresets.filter((p) => ids.has(String(p.id)))
})

const staffingSummary = computed(() => {
  const rows = selectedPresets.value
  if (!rows.length) return null
  let soldiers = 0
  let unknown = 0
  const byKind = new Map()
  for (const row of rows) {
    const st = row.troopStaffing
    const k = row.troopKindId || '—'
    const label = troopKindLabel(k)
    if (!byKind.has(k)) byKind.set(k, { label, teams: 0, staffing: st })
    const ent = byKind.get(k)
    ent.teams += 1
    if (st > 0) soldiers += st
    else unknown += 1
  }
  return {
    teams: rows.length,
    generals: rows.length * 3,
    soldiers,
    unknown,
    byKind: [...byKind.entries()].sort((a, b) => (b[1].staffing || 0) - (a[1].staffing || 0)),
  }
})

const presetPickScrollX = 40 + 108 + 96 * 3 + 100 + 72 + 72

const presetPickColumns = [
  { type: 'selection', fixed: 'left', width: 40 },
  { title: '名称', key: 'name', width: 108, ellipsis: { tooltip: true } },
  {
    title: '主将',
    key: 'g0',
    width: 96,
    ellipsis: { tooltip: true },
    render: (row) => h('span', { class: 'cell-cn' }, generalLabelAt(row, 0)),
  },
  {
    title: '副将1',
    key: 'g1',
    width: 96,
    ellipsis: { tooltip: true },
    render: (row) => h('span', { class: 'cell-cn' }, generalLabelAt(row, 1)),
  },
  {
    title: '副将2',
    key: 'g2',
    width: 96,
    ellipsis: { tooltip: true },
    render: (row) => h('span', { class: 'cell-cn' }, generalLabelAt(row, 2)),
  },
  {
    title: '兵种',
    key: 'troopKindId',
    width: 100,
    ellipsis: { tooltip: true },
    render: (row) => {
      const label = troopKindLabel(row.troopKindId)
      const unique = row.troopKindUnique
      const maxTeams = row.troopKindMaxTeams
      const limited = unique || (maxTeams != null && maxTeams > 0 && maxTeams < 999)
      let suffix = ''
      if (unique) suffix = ' ·唯一'
      else if (maxTeams != null && maxTeams > 1 && maxTeams < 999) suffix = ` ·限${maxTeams}`
      return h(
        'span',
        {
          title: limited
            ? `${troopKindTitle(row.troopKindId)} · ${row.troopKindLimitHint || ''}`
            : troopKindTitle(row.troopKindId),
          class: limited ? 'cell-kind-unique' : '',
        },
        `${label}${suffix}`,
      )
    },
  },
  {
    title: '编制',
    key: 'troopStaffing',
    width: 72,
    align: 'right',
    render: (row) => {
      if (row.troopStaffing > 0) return String(row.troopStaffing)
      if (row.staffing > 0) return String(row.staffing)
      return h('span', { title: row.troopStaffingHint || '' }, '—')
    },
  },
  {
    title: '编组',
    key: 'gameTeamId',
    width: 72,
    align: 'center',
    render: (row) => (row.gameTeamId ? row.gameTeamId : '—'),
  },
]
</script>

<template>
  <div class="page-fill team-deploy-page">
    <section class="panel-surface team-deploy-bar">
      <div class="team-deploy-bar-main">
        <n-form-item label="目标城市" label-placement="left" :show-feedback="false" class="team-deploy-city">
          <n-select
            v-model:value="deployCityKey"
            :options="playerCityOptions"
            :placeholder="citySelectPlaceholder"
            :disabled="!playerCityOptions.length"
            filterable
            size="small"
            style="min-width: 220px; max-width: 280px"
          />
        </n-form-item>
        <n-button
          type="primary"
          size="small"
          :disabled="!store.selectedTeamPresetIds.length || !deployCityKey"
          @click="deploy"
        >
          创建 {{ store.selectedTeamPresetIds.length || 0 }} 支编队
        </n-button>
      </div>
      <p class="team-deploy-hint">
        勾选预设写入存档；二十支可「全选」。每支含 <strong>3 名武将</strong>；「编制」为创建后单队士兵数（healthyNum）。
      </p>
      <p v-if="staffingSummary" class="team-deploy-staffing">
        已选 {{ staffingSummary.teams }} 支 · 武将 {{ staffingSummary.generals }} 人
        <template v-if="staffingSummary.soldiers">
          · 编制合计约 <strong>{{ staffingSummary.soldiers.toLocaleString() }}</strong> 人
        </template>
        <template v-if="staffingSummary.unknown">
          （{{ staffingSummary.unknown }} 支编制随档内模板，需已选存档后刷新本页）
        </template>
      </p>
    </section>

    <section class="panel-surface team-deploy-pick">
      <header class="team-deploy-pick-head">
        <div class="team-deploy-pick-title">
          <n-text strong>选择预设</n-text>
          <n-text depth="3">
            共 {{ store.teamPresets.length }} · 已选 {{ store.selectedTeamPresetIds.length }}
          </n-text>
        </div>
        <div class="team-deploy-pick-actions">
          <n-button v-if="store.teamPresets.length" size="tiny" quaternary type="primary" @click="selectAllPresets">
            全选
          </n-button>
          <n-button
            v-if="store.selectedTeamPresetIds.length"
            size="tiny"
            quaternary
            @click="clearSelection"
          >
            清空勾选
          </n-button>
        </div>
      </header>

      <div v-if="store.teamPresets.length" class="table-stack team-deploy-table-wrap">
        <div ref="tableBodyRef" class="table-stack-body">
          <n-data-table
            striped
            size="small"
            :bordered="false"
            :scroll-x="presetPickScrollX"
            :max-height="tableMaxHeight"
            :columns="presetPickColumns"
            :data="paged"
            :row-key="(r) => String(r.id)"
            v-model:checked-row-keys="checkedPresetKeys"
          />
        </div>
        <div class="table-stack-foot">
          <n-text depth="3">共 {{ store.teamPresets.length }} 条</n-text>
          <n-pagination
            v-model:page="pagination.page"
            v-model:page-size="pagination.pageSize"
            :item-count="store.teamPresets.length"
            :page-sizes="PAGE_SIZE_OPTIONS"
            show-size-picker
            size="small"
          />
        </div>
      </div>
      <n-empty v-else size="small" description="请先在「编队预设」恢复或保存模板" />
    </section>
  </div>
</template>

<style scoped>
.team-deploy-page {
  gap: 10px;
}

.team-deploy-bar {
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.team-deploy-bar-main {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 12px;
}

.team-deploy-city {
  margin-bottom: 0;
  flex: 0 1 auto;
}

.team-deploy-staffing {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--n-text-color-3);
}

.team-deploy-hint {
  margin: 0;
  font-size: 12px;
  color: var(--app-ink-muted, var(--n-text-color-3));
  line-height: 1.45;
}

.team-deploy-pick {
  padding: 10px 12px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1 1 auto;
  min-height: 0;
}

.team-deploy-pick-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.team-deploy-pick-title {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px;
}

.team-deploy-pick-actions {
  display: flex;
  gap: 4px;
}

.team-deploy-table-wrap {
  flex: 1 1 auto;
  min-height: 0;
}

.team-deploy-table-wrap :deep(.cell-cn) {
  font-size: 13px;
}

.team-deploy-table-wrap :deep(.cell-kind-unique) {
  color: var(--app-accent-deep, #b45309);
  font-weight: 600;
}
</style>
