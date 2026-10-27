<script setup>
import { logText, clearLog } from '../log'
</script>

<template>
  <div class="page-fill log-page">
    <n-space justify="space-between" align="center" wrap class="log-toolbar">
      <p class="hint">各页操作、报错与城市「一致性问题」等都会追加到这里。</p>
      <n-button size="small" quaternary @click="clearLog">清空</n-button>
    </n-space>
    <n-card size="small" title="记录" class="log-card">
      <div class="log-scroll-wrap">
        <n-scrollbar class="log-scrollbar">
          <pre class="log-body">{{ logText || '（暂无记录）' }}</pre>
        </n-scrollbar>
      </div>
    </n-card>
  </div>
</template>

<style scoped>
.log-page {
  min-height: 0;
  overflow: hidden;
}

.log-toolbar {
  flex-shrink: 0;
}

.log-card {
  flex: 1 1 0;
  min-height: 0;
  overflow: hidden;
}

.log-card :deep(.n-card) {
  height: 100%;
  max-height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
  box-sizing: border-box;
}

.log-card :deep(.n-card-header) {
  flex-shrink: 0;
}

.log-card :deep(.n-card__content) {
  flex: 1 1 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 8px 12px 12px;
  box-sizing: border-box;
}

.log-scroll-wrap {
  flex: 1 1 0;
  min-height: 0;
  position: relative;
}

.log-scrollbar {
  position: absolute;
  inset: 0;
}

.log-scrollbar :deep(.n-scrollbar-container) {
  max-height: 100%;
}

.log-scrollbar :deep(.n-scrollbar-content) {
  box-sizing: border-box;
  padding: 4px 8px 12px 2px;
}

.log-body {
  margin: 0;
  font-family: Consolas, 'Cascadia Mono', 'Microsoft YaHei UI', monospace;
  font-size: 13px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--n-text-color-1);
}
</style>
