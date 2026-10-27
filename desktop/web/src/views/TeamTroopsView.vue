<script setup>
import { computed, h, ref } from 'vue'
import { store, loadTeamsInSave } from '../store'
import { useTableMaxHeight } from '../useTableMaxHeight'
import { useTroopKindLabel } from '../useTroopKindLabel'

const { troopKindLabel, troopKindTitle } = useTroopKindLabel()

const layoutRef = ref(null)
const loading = ref(false)
const tableMaxHeight = useTableMaxHeight(layoutRef, 220)

const saveTroops = computed(() => store.teamsInSave || [])

async function reload() {
  loading.value = true
  try {
    await loadTeamsInSave()
  } finally {
    loading.value = false
  }
}

const saveTroopColumns = [
  { title: '主将名', key: 'name', width: 100, ellipsis: { tooltip: true } },
  { title: '主将', key: 'g0', ellipsis: { tooltip: true }, render: (r) => r.generals_cn?.[0] || '—' },
  { title: '副将1', key: 'g1', ellipsis: { tooltip: true }, render: (r) => r.generals_cn?.[1] || '—' },
  { title: '副将2', key: 'g2', ellipsis: { tooltip: true }, render: (r) => r.generals_cn?.[2] || '—' },
  {
    title: '兵种',
    key: 'troopKindId',
    width: 96,
    ellipsis: { tooltip: true },
    render: (r) => {
      const label = r.troopKindCn || troopKindLabel(r.troopKindId)
      const title = troopKindTitle(r.troopKindId)
      return h('span', { title }, label)
    },
  },
  { title: '游戏编组', key: 'gameTeamId', width: 80, render: (r) => (r.gameTeamId ? r.gameTeamId : '—') },
  { title: 'troopId', key: 'troopId', width: 96 },
]
</script>

<template>
  <div ref="layoutRef" class="page-fill team-troops-page">
    <p class="hint">
      当前存档中的部队：<strong>每行 = 一支三人编队</strong>（主将 + 副将1 + 副将2）。创建新编队在「创建编队」；模板在「编队预设」。
    </p>

    <section class="panel-surface team-troops-panel">
      <div class="team-troops-head">
        <n-text depth="3">共 {{ saveTroops.length }} 支</n-text>
        <n-button size="small" quaternary :loading="loading" @click="reload">刷新</n-button>
      </div>
      <n-data-table
        striped
        size="small"
        class="team-troops-table"
        :loading="loading"
        :max-height="tableMaxHeight"
        :columns="saveTroopColumns"
        :data="saveTroops"
        :row-key="(r) => String(r.troopId)"
      />
    </section>
  </div>
</template>

<style scoped>
.team-troops-page {
  min-height: 0;
}

.team-troops-panel {
  flex: 1 1 auto;
  min-height: 0;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.team-troops-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.team-troops-table {
  flex: 1 1 auto;
  min-height: 0;
}
</style>
