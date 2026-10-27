<script setup>
import { NConfigProvider, NDialogProvider, NMessageProvider } from 'naive-ui'
import { themeOverrides } from './theme'
import AppInner from './AppInner.vue'
</script>

<template>
  <n-config-provider :theme-overrides="themeOverrides">
    <n-dialog-provider>
      <n-message-provider>
        <AppInner />
      </n-message-provider>
    </n-dialog-provider>
  </n-config-provider>
</template>
