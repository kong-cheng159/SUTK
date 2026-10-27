<script setup>
import { ref, computed, h } from 'vue'
import { NInputNumber, NCheckbox, NButton } from 'naive-ui'
import { store } from '../store'
import { useTableMaxHeight } from '../useTableMaxHeight'

const tableWrapRef = ref(null)
const tableMaxHeight = useTableMaxHeight(tableWrapRef)
const diploScrollX = 56 + 100 + 52 + 80 + 64 + 64 + 88 + 88 + 84 + 18

const emit = defineEmits(['write-one'])

const columns = computed(() => [
  { title: '势力', key: 'fid', width: 56 },
  { title: '君主', key: 'king', width: 100 },
  { title: '已灭', key: 'destroyed', width: 52, render: (r) => (r.destroyed ? '是' : '') },
  {
    title: '关系',
    key: 'relation',
    width: 80,
    render(row) {
      return h(NInputNumber, {
        size: 'small',
        showButton: false,
        value: row.edit.relation,
        onUpdateValue: (v) => {
          row.edit.relation = v
        },
      })
    },
  },
  {
    title: '同盟',
    key: 'friend',
    width: 64,
    render(row) {
      return h(NCheckbox, {
        checked: row.edit.friend,
        onUpdateChecked: (v) => {
          row.edit.friend = v
        },
      })
    },
  },
  {
    title: '停战',
    key: 'armistice',
    width: 64,
    render(row) {
      return h(NCheckbox, {
        checked: row.edit.armistice,
        onUpdateChecked: (v) => {
          row.edit.armistice = v
        },
      })
    },
  },
  {
    title: '人情(我)',
    key: 'favour',
    width: 88,
    render(row) {
      return h(NInputNumber, {
        size: 'small',
        showButton: false,
        value: row.edit.favour,
        onUpdateValue: (v) => {
          row.edit.favour = v
        },
      })
    },
  },
  {
    title: '人情(他)',
    key: 'favour_other',
    width: 88,
    render(row) {
      return h(NInputNumber, {
        size: 'small',
        showButton: false,
        value: row.edit.favour_other,
        onUpdateValue: (v) => {
          row.edit.favour_other = v
        },
      })
    },
  },
  {
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
  },
])
</script>

<template>
  <div class="page-fill">
    <p class="hint">{{ store.diploHint }}</p>
    <slot name="toolbar" />
    <div ref="tableWrapRef" class="table-flex">
      <n-data-table
        striped
        size="small"
        :max-height="tableMaxHeight"
        :scroll-x="diploScrollX"
        :columns="columns"
        :data="store.diplo"
        :row-key="(r) => r.fid"
        :row-class-name="(r) => (r.destroyed ? 'row-dead' : '')"
      />
    </div>
  </div>
</template>

<style scoped>
:deep(.row-dead td) {
  opacity: 0.55;
}
</style>
