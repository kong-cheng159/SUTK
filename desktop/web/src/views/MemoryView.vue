<script setup>
import { computed } from 'vue'
import { store } from '../store'

const memText = computed(() => {
  const m = store.mem
  if (!m) return '加载中…'
  if (m.error) return m.error
  return [
    m.admin ? '当前是管理员，可以读写游戏内存。' : '当前不是管理员。若游戏由管理员 Steam 启动，扫描会被拒绝。',
    m.game ? `游戏进程 PID ${m.game.pid}，约 ${Math.round(m.game.kb / 1024)} MB。` : '没有找到正在运行的游戏。',
    `当前候选 ${m.hits} 处` +
      (m.value != null ? `，上次数值 ${m.value}` : '') +
      (m.sample?.length ? `。前几个：${m.sample.map((x) => '0x' + x.toString(16)).join(' ')}` : ''),
  ].join('\n')
})
</script>

<template>
  <n-scrollbar style="max-height:100%">
    <n-space vertical size="medium">
      <n-alert type="warning" :bordered="false">
        只扫描 SUTK-Win64-Shipping.exe。先在游戏里改数值，再用新数值过滤，候选少了再写入。
      </n-alert>
      <n-card size="small">
        <pre style="margin:0;white-space:pre-wrap">{{ memText }}</pre>
      </n-card>
      <n-space wrap align="center">
        <n-select
          v-model:value="store.memField"
          style="width:120px"
          :options="[
            { label: '金钱', value: 'money' },
            { label: '兵役', value: 'conscription' },
            { label: '粮食', value: 'food' },
          ]"
        />
        <n-input v-model:value="store.memSeed" placeholder="或直接填种子" style="width:160px" />
        <slot name="scan" />
      </n-space>
      <n-space wrap align="center">
        <n-input v-model:value="store.memFilter" placeholder="过滤成新数值" style="width:160px" />
        <slot name="filter" />
        <n-input v-model:value="store.memWrite" placeholder="写入值" style="width:160px" />
        <slot name="write" />
        <slot name="elevate" />
      </n-space>
    </n-space>
  </n-scrollbar>
</template>
