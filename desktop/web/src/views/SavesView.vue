<script setup>
import { ref, computed } from 'vue'
import { store } from '../store'
import { STATS, STAT_NAME } from '../constants'
import { useTableMaxHeight } from '../useTableMaxHeight'

const layoutRef = ref(null)
const tableMaxHeight = useTableMaxHeight(layoutRef)
/** 预留底部操作栏高度 */
const tableHeight = computed(() => Math.max(220, tableMaxHeight.value))
const configScrollHeight = computed(() => Math.max(160, tableMaxHeight.value - 8))

const modules = computed(() => store.status?.modules || [])
const capLabel = computed(() => store.status?.cap_label || {})
const capKeys = computed(() => Object.keys(store.caps))

const saveScrollX = 40 + 220 + 112 + 152 + 72 + 56

const saveColumns = [
  { type: 'selection', width: 40 },
  { title: '存档', key: 'name', width: 220, ellipsis: { tooltip: true } },
  { title: '势力', key: 'player', width: 112, ellipsis: { tooltip: true } },
  { title: '时间', key: 'time', width: 152 },
  { title: '状态', key: 'state', width: 72, align: 'center' },
  {
    title: '备份',
    key: 'has_orig',
    width: 56,
    align: 'center',
    render: (r) => (r.has_orig ? '有' : '—'),
  },
]

const saveRows = computed(() => store.saves)
const checkedSaveKeys = computed({
  get: () => store.saves.filter((s) => store.saveChecks[s.name]).map((s) => s.name),
  set: (keys) => {
    const set = new Set(keys)
    store.saves.forEach((s) => {
      store.saveChecks[s.name] = set.has(s.name)
    })
  },
})
</script>

<template>
  <div class="page-fill saves-page">
    <n-alert v-if="store.status && store.status.saves_dir_ok === false" type="error" :bordered="false" class="saves-tip">
      存档目录不可用：{{ store.status.saves_dir }}。请到「设置 → 存档路径」修改。
    </n-alert>
    <n-alert v-else type="info" :bordered="false" class="saves-tip">
      勾选存档和模块后再应用。改完请退出到主菜单重新读档。
    </n-alert>

    <div ref="layoutRef" class="saves-layout">
      <section class="saves-list">
        <div class="saves-list-head">
          <n-text strong>存档列表</n-text>
          <n-text depth="3">共 {{ saveRows.length }} 个 · 已选 {{ checkedSaveKeys.length }} 个</n-text>
        </div>
        <n-data-table
          class="saves-table"
          striped
          size="small"
          :max-height="tableHeight"
          :scroll-x="saveScrollX"
          :scrollbar-props="{ contentStyle: 'padding-bottom: 12px' }"
          :columns="saveColumns"
          :data="saveRows"
          :row-key="(r) => r.name"
          v-model:checked-row-keys="checkedSaveKeys"
        />
      </section>

      <aside class="saves-side">
        <n-card class="saves-config" title="模块与目标值" size="small" :bordered="true">
          <n-scrollbar :style="{ maxHeight: configScrollHeight + 'px' }">
            <div class="saves-config-form">
              <n-checkbox-group v-model:value="store.sections">
                <n-space vertical size="small">
                  <n-checkbox
                    v-for="m in modules"
                    :key="m.key"
                    :value="m.key"
                    :label="m.name"
                  />
                </n-space>
              </n-checkbox-group>
              <n-divider style="margin:12px 0" />
              <n-form label-placement="left" label-width="88" size="small">
                <n-form-item v-for="k in capKeys" :key="'c' + k" :label="capLabel[k] || k">
                  <n-input-number v-model:value="store.caps[k]" :show-button="false" style="width:100%" />
                </n-form-item>
                <n-form-item v-for="k in STATS" :key="'s' + k" :label="STAT_NAME[k]">
                  <n-input-number v-model:value="store.stats[k]" :show-button="false" style="width:100%" />
                </n-form-item>
                <n-form-item label="作用范围">
                  <n-select
                    v-model:value="store.scope"
                    :options="[
                      { label: '仅玩家势力', value: 'player' },
                      { label: '所有势力（含 AI）', value: 'all' },
                    ]"
                  />
                </n-form-item>
                <n-form-item label=" ">
                  <n-checkbox v-model:checked="store.force">强制重写</n-checkbox>
                </n-form-item>
              </n-form>
            </div>
          </n-scrollbar>
        </n-card>
      </aside>
    </div>

    <footer class="saves-actions-bar">
      <slot name="actions" />
    </footer>
  </div>
</template>

<style scoped>
.saves-page {
  min-height: 0;
  overflow: hidden;
}

.saves-tip {
  flex-shrink: 0;
}

.saves-layout {
  flex: 1 1 0;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(320px, 1fr) 360px;
  gap: 14px;
  overflow: hidden;
}

.saves-list {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 10px 12px 12px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  background: var(--app-surface);
  box-shadow: var(--app-shadow-sm);
  box-sizing: border-box;
  overflow: hidden;
}

.saves-list-head {
  flex-shrink: 0;
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.saves-table {
  flex: 1 1 0;
  min-height: 0;
  width: 100%;
}

.saves-side {
  min-height: 0;
  min-width: 0;
  overflow: hidden;
}

.saves-config :deep(.n-card-header) {
  padding: 10px 14px 8px;
}

.saves-config :deep(.n-card__content) {
  padding: 0 0 12px;
}

.saves-config-form {
  padding: 0 14px 4px;
}

.saves-actions-bar {
  flex-shrink: 0;
  margin-top: 10px;
  padding: 14px 16px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  background: var(--app-surface);
  box-shadow: var(--app-shadow-sm);
}

.saves-actions-bar :deep(.n-space) {
  width: 100%;
}

.saves-actions-bar :deep(.n-space > div) {
  gap: 10px !important;
}

.saves-table :deep(.n-data-table-wrapper) {
  width: 100%;
}
</style>
