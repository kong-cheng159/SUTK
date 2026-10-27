<script setup>
import { store } from '../store'
</script>

<template>
  <n-scrollbar style="max-height:100%">
    <article class="md" v-html="store.guideHtml" />
  </n-scrollbar>
</template>
