<script setup>
import { h, ref } from 'vue'
import { NButton, NInput, useMessage } from 'naive-ui'
import { store } from '../store'
import { api } from '../api'
import { useGeneralLabel } from '../useGeneralLabel'
import { useTroopKindLabel } from '../useTroopKindLabel'

const message = useMessage()
const { generalLabel } = useGeneralLabel()
const { troopKindLabel, troopKindTitle } = useTroopKindLabel()

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

function removePreset(index) {
  store.teamPresets.splice(index, 1)
}

async function savePresets() {
  const data = await api('/api/team-presets/save', { presets: store.teamPresets })
  store.teamPresets = data.presets || []
  message.success('三人编队预设已保存')
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

const presetScrollX = 96 + 88 + 88 + 88 + 96 + 72 + 64 + 88

const presetColumns = [
  {
    title: '名称',
    key: 'name',
    width: 96,
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
    width: 88,
    ellipsis: { tooltip: true },
    render: (row) => generalLabel(row.generals?.[0]),
  },
  {
    title: '副将1',
    key: 'g1',
    width: 88,
    ellipsis: { tooltip: true },
    render: (row) => generalLabel(row.generals?.[1]),
  },
  {
    title: '副将2',
    key: 'g2',
    width: 88,
    ellipsis: { tooltip: true },
    render: (row) => generalLabel(row.generals?.[2]),
  },
  {
    title: '兵种',
    key: 'troopKindId',
    width: 96,
    ellipsis: { tooltip: true },
    render: (row) =>
      h('span', { title: troopKindTitle(row.troopKindId) }, troopKindLabel(row.troopKindId)),
  },
  {
    title: '游戏编组',
    key: 'gameTeamId',
    width: 72,
    render: (row) => (row.gameTeamId ? row.gameTeamId : '—'),
  },
  {
    title: '兵力',
    key: 'staffing',
    width: 64,
    render: (row) => (row.staffing ? row.staffing : '自动'),
  },
  {
    title: '操作',
    key: 'actions',
    width: 88,
    fixed: 'right',
    render: (row) => {
      const index = store.teamPresets.indexOf(row)
      return h('div', { class: 'preset-actions' }, [
        h(
          NButton,
          { size: 'tiny', quaternary: true, onClick: () => openEditPreset(row) },
          { default: () => '编辑' },
        ),
        h(
          NButton,
          {
            size: 'tiny',
            quaternary: true,
            type: 'error',
            onClick: () => removePreset(index),
          },
          { default: () => '删' },
        ),
      ])
    },
  },
]
</script>

<template>
  <div class="page-fill team-presets-page">
    <p class="hint">
      维护<strong>三人编队模板</strong>（主将 + 副将1 + 副将2）。内置十支：编组1 霍骠垒、卫骧城、江骏岳；编组2 韩澜靖、秦霆烈、段烬壁、沈岳川、赵朔川、周晟垒、卫霄城。
      保存后请到侧栏<strong>创建编队</strong>勾选并写入存档。
    </p>

    <section class="panel-surface team-presets-panel">
      <p v-if="store.current && !store.generals.length" class="teams-table-note">
        已选存档但未加载武将名录；主将列显示 GUID。打开「武将」页后可显示中文名。
      </p>
      <n-data-table
        v-if="store.teamPresets.length"
        striped
        size="small"
        class="team-presets-table"
        :scroll-x="presetScrollX"
        :columns="presetColumns"
        :data="store.teamPresets"
        :row-key="(r) => String(r.id)"
      />
      <n-empty v-else size="small" description="暂无预设" />
      <n-space wrap class="team-presets-toolbar">
        <n-button size="small" @click="addPreset">新建预设</n-button>
        <n-button size="small" @click="importFromSave">从存档导入每支部队</n-button>
        <n-button type="primary" size="small" @click="savePresets">保存预设</n-button>
      </n-space>
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
.team-presets-panel {
  padding: 12px;
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.teams-table-note {
  margin: 0 0 8px;
  font-size: 12px;
  color: var(--n-text-color-3);
}

.team-presets-toolbar {
  margin-top: 10px;
}

.team-presets-table :deep(.preset-actions) {
  display: flex;
  gap: 2px;
}

.team-presets-table {
  flex: 1 1 auto;
}
</style>
