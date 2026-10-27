<script setup>
import { computed, h, ref, watch } from 'vue'
import { useMessage, useDialog } from 'naive-ui'
import { store, loadTeamsInSave } from '../store'
import { api } from '../api'
import { appendLog } from '../log'
import { useGeneralLabel } from '../useGeneralLabel'
import { useTroopKindLabel } from '../useTroopKindLabel'

const message = useMessage()
const dialog = useDialog()
const { generalLabel } = useGeneralLabel()
const { troopKindLabel, troopKindTitle } = useTroopKindLabel()

const deployCityKey = ref('')

const playerFid = computed(() => store.status?.player ?? '')

const playerCityOptions = computed(() =>
  store.cities
    .filter((c) => String(c.fid) === String(playerFid.value))
    .map((c) => ({
      label: `${c.cn || c.key}${c.capital ? ' ★' : ''}`,
      value: c.key,
    })),
)

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
    content: `在「${cityLabel}」创建 ${n} 支部队？\n每支 = 主将 + 2 副将；武将须空闲且不在其他队。`,
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

const presetPickScrollX = 40 + 96 + 88 + 88 + 88 + 72 + 72

const presetPickColumns = [
  { type: 'selection', fixed: 'left', width: 40 },
  { title: '名称', key: 'name', width: 96, ellipsis: { tooltip: true } },
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
    title: '编组',
    key: 'gameTeamId',
    width: 72,
    render: (row) => (row.gameTeamId ? row.gameTeamId : '—'),
  },
]
</script>

<template>
  <div class="page-fill team-deploy-page">
    <p class="hint">
      勾选预设、选目标城后写入存档。模板在<strong>编队预设</strong>维护；创建后请到<strong>存档部队</strong>核对。
    </p>

    <section class="panel-surface team-deploy-bar">
      <n-form-item label="目标城市" label-placement="left" :show-feedback="false" class="team-deploy-city">
        <n-select
          v-model:value="deployCityKey"
          :options="playerCityOptions"
          placeholder="选择城市"
          filterable
          style="min-width: 200px"
        />
      </n-form-item>
      <n-button
        type="primary"
        :disabled="!store.selectedTeamPresetIds.length || !deployCityKey"
        @click="deploy"
      >
        创建选中的 {{ store.selectedTeamPresetIds.length || 0 }} 支编队
      </n-button>
    </section>

    <section class="panel-surface team-deploy-pick">
      <div class="team-deploy-pick-head">
        <n-text strong>选择预设</n-text>
        <n-text depth="3">共 {{ store.teamPresets.length }} 条 · 已选 {{ store.selectedTeamPresetIds.length }} 条</n-text>
      </div>
      <n-data-table
        v-if="store.teamPresets.length"
        striped
        size="small"
        :scroll-x="presetPickScrollX"
        :columns="presetPickColumns"
        :data="store.teamPresets"
        :row-key="(r) => String(r.id)"
        v-model:checked-row-keys="checkedPresetKeys"
      />
      <n-empty v-else size="small" description="请先在「编队预设」添加并保存模板" />
    </section>
  </div>
</template>

<style scoped>
.team-deploy-page {
  gap: 10px;
}

.team-deploy-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 12px;
  padding: 10px 12px;
}

.team-deploy-city {
  margin-bottom: 0;
}

.team-deploy-pick {
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1 1 auto;
  min-height: 0;
}

.team-deploy-pick-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
</style>
