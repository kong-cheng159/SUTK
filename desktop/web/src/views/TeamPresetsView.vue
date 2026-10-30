<script setup>
import { computed, h, ref, watch } from 'vue'
import { NButton, NInput, NText, NPagination, useMessage } from 'naive-ui'
import { store } from '../store'
import { api } from '../api'
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
const { generalLabelAt } = useGeneralLabel()
const { troopKindLabel, troopKindTitle } = useTroopKindLabel()

const tableBodyRef = ref(null)
const tableMaxHeight = useTableMaxHeight(tableBodyRef, 200)
const pagination = useTablePagination(20)
const paged = usePagedRows(computed(() => store.teamPresets), pagination)

watch(
  () => store.teamPresets.length,
  () => resetPaginationPage(pagination),
)

const showEditModal = ref(false)
const editingPreset = ref(null)

function openEditPreset(row) {
  editingPreset.value = {
    ...row,
    generals: [...(row.generals || ['None', 'None', 'None'])].slice(0, 3),
  }
  while (editingPreset.value.generals.length < 3) editingPreset.value.generals.push('None')
  showEditModal.value = true
}

function applyEditPreset() {
  if (!editingPreset.value) return
  const i = store.teamPresets.findIndex((p) => p.id === editingPreset.value.id)
  if (i >= 0) Object.assign(store.teamPresets[i], editingPreset.value)
  showEditModal.value = false
}

function closeEditModal() {
  showEditModal.value = false
  editingPreset.value = null
}

function updateEditingGenerals(v) {
  if (!editingPreset.value) return
  editingPreset.value.generals = v
    .split(/[,，]/)
    .map((x) => x.trim() || 'None')
    .slice(0, 3)
  while (editingPreset.value.generals.length < 3) editingPreset.value.generals.push('None')
}

async function reloadSaveTroops() {
  if (!store.current) return
  const data = await api('/api/teams?name=' + encodeURIComponent(store.current))
  return data.teams || []
}

function addPreset() {
  const n = (store.teamPresets?.length || 0) + 1
  store.teamPresets.push({
    id: `preset_${n}`,
    name: `霍骠垒式-${n}`,
    troopKindId: '49_2',
    generals: ['None', 'None', 'None'],
    staffing: 0,
  })
}

function removePreset(row) {
  const index = store.teamPresets.findIndex((p) => p.id === row.id)
  if (index >= 0) store.teamPresets.splice(index, 1)
}

async function savePresets() {
  const data = await api('/api/team-presets/save', {
    presets: store.teamPresets,
    name: store.current || undefined,
  })
  store.teamPresets = data.presets || []
  store.guidLabels = data.guid_labels || {}
  message.success('三人编队预设已保存')
}

async function repairPresets() {
  const data = await api('/api/team-presets/repair', { name: store.current || undefined })
  store.teamPresets = data.presets || []
  store.guidLabels = data.guid_labels || {}
  store.selectedTeamPresetIds = store.selectedTeamPresetIds.filter((id) =>
    store.teamPresets.some((p) => String(p.id) === String(id)),
  )
  message.success(data.lines?.[0] || `已整理为 ${store.teamPresets.length} 条`)
}

async function resetBuiltinPresets() {
  const data = await api('/api/team-presets/reset-builtin', { name: store.current || undefined })
  store.teamPresets = data.presets || []
  store.guidLabels = data.guid_labels || {}
  store.selectedTeamPresetIds = store.teamPresets.map((p) => String(p.id))
  const tip = (data.lines || []).join('\n')
  message.success(tip || '已恢复内置预设', { duration: tip.includes('\n') ? 8000 : 3000 })
}

async function applyGroupingPresets() {
  const data = await api('/api/team-presets/apply-grouping', { name: store.current || undefined })
  store.teamPresets = data.presets || []
  store.guidLabels = data.guid_labels || {}
  const tip = (data.lines || []).join('\n')
  message.success(tip || '已应用编组规则', { duration: 8000 })
}

async function importFromSave() {
  if (!store.current) {
    message.warning('请先在顶部选择存档')
    return
  }
  const troops = await reloadSaveTroops()
  if (!troops.length) {
    message.info('当前存档里没有部队')
    return
  }
  for (const t of troops) {
    store.teamPresets.push({
      id: `troop_${t.troopId}_${Date.now() % 10000}`,
      name: t.name || `部队 ${t.troopId}`,
      troopKindId: t.troopKindId || '55_2',
      generals: [...(t.generals || ['None', 'None', 'None'])].slice(0, 3),
      staffing: 0,
    })
  }
  message.success(`已导入 ${troops.length} 支三人编队（记得保存预设）`)
}

const presetScrollX = 108 + 96 * 3 + 100 + 72 + 64 + 88

const presetColumns = [
  {
    title: '名称',
    key: 'name',
    width: 108,
    ellipsis: { tooltip: true },
    render: (row) =>
      h(NInput, {
        size: 'small',
        value: row.name,
        onUpdateValue: (v) => {
          row.name = v
        },
      }),
  },
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
      if (row.troopKindUnique) {
        return h(
          'span',
          { class: 'cell-kind-unique', title: row.troopKindLimitHint || '唯一兵种' },
          `${label} ·唯一`,
        )
      }
      const maxTeams = row.troopKindMaxTeams
      if (maxTeams != null && maxTeams > 1 && maxTeams < 999) {
        return h(
          'span',
          { class: 'cell-kind-unique', title: row.troopKindLimitHint || `最多 ${maxTeams} 支` },
          `${label} ·限${maxTeams}`,
        )
      }
      return h('span', { title: troopKindTitle(row.troopKindId) }, label)
    },
  },
  {
    title: '编组',
    key: 'gameTeamId',
    width: 72,
    align: 'center',
    render: (row) => (row.gameTeamId ? row.gameTeamId : '—'),
  },
  {
    title: '兵力',
    key: 'staffing',
    width: 64,
    align: 'center',
    render: (row) => (row.staffing ? row.staffing : '自动'),
  },
  {
    title: '操作',
    key: 'actions',
    width: 88,
    fixed: 'right',
    render: (row) =>
      h('div', { class: 'preset-actions' }, [
        h(
          NButton,
          { size: 'tiny', quaternary: true, type: 'primary', onClick: () => openEditPreset(row) },
          { default: () => '编辑' },
        ),
        h(
          NButton,
          {
            size: 'tiny',
            quaternary: true,
            type: 'error',
            onClick: () => removePreset(row),
          },
          { default: () => '删' },
        ),
      ]),
  },
]
</script>

<template>
  <div class="page-fill team-presets-page">
    <p class="hint team-presets-hint">
      三人编队模板（主将 + 2 副将）。内置二十支均为<strong>特殊兵种</strong>优先（前 10 原版 30 将，后 10 支
      <code>batch2_</code> 为另一批特殊兵）；完整列表见 <code>desktop/data/special_troop_kinds.json</code>。
      保存后在「创建编队」勾选写入存档。编组规则：<strong>1/2 组</strong>各 3 枪 + 2 盾 + 2 弓，<strong>3 组</strong>为全部骑兵（见
      <code>desktop/data/team_preset_group_rules.json</code>）。
    </p>

    <section class="panel-surface team-presets-panel">
      <header class="team-presets-head">
        <n-text depth="3">共 {{ store.teamPresets.length }} 条</n-text>
        <div class="team-presets-actions">
          <n-button size="small" quaternary @click="addPreset">新建</n-button>
          <n-button size="small" quaternary @click="importFromSave">从存档导入</n-button>
          <n-button size="small" secondary @click="repairPresets">去重</n-button>
          <n-button size="small" secondary @click="resetBuiltinPresets">恢复内置</n-button>
          <n-button size="small" secondary @click="applyGroupingPresets">按规则编组</n-button>
          <n-button type="primary" size="small" @click="savePresets">保存</n-button>
        </div>
      </header>

      <p v-if="store.current && !store.generals.length" class="teams-table-note">
        已选存档但未加载武将名录；请先打开「武将」页以显示中文名。
      </p>

      <div v-if="store.teamPresets.length" class="table-stack team-presets-table-wrap">
        <div ref="tableBodyRef" class="table-stack-body">
          <n-data-table
            striped
            size="small"
            :bordered="false"
            :scroll-x="presetScrollX"
            :max-height="tableMaxHeight"
            :columns="presetColumns"
            :data="paged"
            :row-key="(r) => String(r.id)"
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
      <n-empty v-else size="small" description="暂无预设，可点「恢复内置」" />
    </section>

    <n-modal
      v-model:show="showEditModal"
      preset="card"
      title="编辑预设"
      style="width: min(480px, 92vw)"
      :mask-closable="false"
      @after-leave="editingPreset = null"
    >
      <n-space v-if="editingPreset" vertical size="small">
        <n-input v-model:value="editingPreset.id" size="small" placeholder="预设 ID" />
        <n-input v-model:value="editingPreset.name" size="small" placeholder="名称" />
        <n-input v-model:value="editingPreset.troopKindId" size="small" placeholder="兵种 troopKindId" />
        <n-input
          :value="(editingPreset.generals || []).join(', ')"
          size="small"
          placeholder="主将, 副将1, 副将2（GUID；空位 None）"
          @update:value="updateEditingGenerals"
        />
        <n-input-number v-model:value="editingPreset.staffing" size="small" :min="0" placeholder="兵力 0=自动" />
        <n-input-number
          v-model:value="editingPreset.gameTeamId"
          size="small"
          :min="0"
          placeholder="游戏编组号（可选）"
        />
      </n-space>
      <template #footer>
        <n-space justify="end">
          <n-button @click="closeEditModal">取消</n-button>
          <n-button type="primary" @click="applyEditPreset">确定</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<style scoped>
.team-presets-page {
  gap: 10px;
}

.team-presets-hint {
  margin-bottom: 0;
}

.team-presets-hint code {
  font-size: 12px;
}

.team-presets-panel {
  padding: 10px 12px 12px;
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  min-height: 0;
  gap: 8px;
}

.team-presets-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px 12px;
}

.team-presets-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: flex-end;
}

.teams-table-note {
  margin: 0;
  font-size: 12px;
  color: var(--n-text-color-3);
}

.team-presets-table-wrap {
  flex: 1 1 auto;
  min-height: 0;
}

.team-presets-table-wrap :deep(.cell-cn) {
  font-size: 13px;
}

.team-presets-table-wrap :deep(.preset-actions) {
  display: flex;
  gap: 2px;
  justify-content: flex-end;
}

.team-presets-table-wrap :deep(.cell-kind-unique) {
  color: var(--app-accent-deep, #b45309);
  font-weight: 600;
}
</style>
