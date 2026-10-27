<script setup>
import { store } from '../store'
</script>

<template>
  <n-scrollbar style="max-height:100%">
    <n-space vertical size="large">
      <slot name="toolbar" />
      <n-card title="体检结果" size="small">
        <pre style="margin:0;white-space:pre-wrap;font-size:13px">{{ store.auditText || '点击「存档体检」开始检查。' }}</pre>
      </n-card>
      <div>
        <h3 style="margin:0 0 8px">历史版本</h3>
        <p class="hint">回滚前会先把当前内容再存一份。</p>
        <n-empty v-if="!store.history.length" description="还没有历史快照" />
        <n-card v-for="s in store.history" :key="s.name" size="small" style="margin-bottom:8px">
          <template #header>{{ s.name }}</template>
          <template #header-extra>
            <n-text depth="3">快照 {{ s.snaps }} · 原始档 {{ s.orig ? '有' : '无' }}</n-text>
          </template>
          <n-space vertical size="small">
            <n-space v-for="v in s.versions" :key="v.file" justify="space-between">
              <n-text>{{ v.kind }} {{ v.when }} {{ v.note }} {{ Math.round(v.size / 1024) }}K</n-text>
              <slot name="undo" :save="s.name" :file="v.file" />
            </n-space>
          </n-space>
        </n-card>
      </div>
    </n-space>
  </n-scrollbar>
</template>
