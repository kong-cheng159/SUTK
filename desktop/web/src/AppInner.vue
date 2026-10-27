<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import {
  NLayout,
  NLayoutHeader,
  NLayoutSider,
  NLayoutContent,
  NMenu,
  NSelect,
  NTag,
  NButton,
  NText,
  useDialog,
  useMessage,
} from 'naive-ui'
import { MENU } from './constants'
import { menuIcon } from './menuIcons'
import { appendLog } from './log'
import { api } from './api'
import { renderMarkdown } from './markdown'
import {
  store,
  boot,
  loadSaves,
  loadGenerals,
  loadExtern,
  loadCities,
  loadDiplo,
  loadAudit,
  loadHistory,
  loadMem,
  loadGuide,
  loadOrphans,
  refreshPage,
  configBody,
  pathConfigBody,
  namesOrCurrent,
  applyStatusCfg,
} from './store'
import SavesView from './views/SavesView.vue'
import GeneralsView from './views/GeneralsView.vue'
import CitiesView from './views/CitiesView.vue'
import DiploView from './views/DiploView.vue'
import CheckView from './views/CheckView.vue'
import MemoryView from './views/MemoryView.vue'
import GuideView from './views/GuideView.vue'
import SettingsView from './views/SettingsView.vue'
import LogView from './views/LogView.vue'

const page = ref('saves')
const citiesRef = ref(null)
const bootFailed = ref('')
const dialog = useDialog()
const message = useMessage()

const saveOptions = computed(() =>
  store.saves.map((s) => ({
    label: `${s.name} · ${s.player || s.state}`,
    value: s.name,
  })),
)

const menuOptions = MENU.map((m) => ({
  label: m.label,
  key: m.key,
  icon: menuIcon(m.key),
}))

function confirm(content, fn) {
  dialog.warning({
    title: '请确认',
    content,
    positiveText: '继续',
    negativeText: '取消',
    onPositiveClick: async () => {
      await fn()
      return true
    },
  })
}

async function run(fn) {
  try {
    store.loading = true
    await fn()
  } catch (e) {
    appendLog(e.message)
    if (e.data?.need_admin) appendLog('点「管理员重新打开」，在 UAC 里选是。')
    message.error(e.message || '操作失败')
  } finally {
    store.loading = false
  }
}

async function onPage(key) {
  page.value = key
  if (key === 'guide') await loadGuide(renderMarkdown)
  await refreshPage(key)
}

watch(
  () => store.current,
  () => refreshPage(page.value),
)

/** 首屏不用全屏 Spin，避免未起 API 时看起来像空白页 */
async function startup() {
  bootFailed.value = ''
  try {
    await boot()
  } catch (e) {
    bootFailed.value = e.message || '无法连接后端'
    appendLog(bootFailed.value)
    message.error(bootFailed.value, { duration: 10_000 })
  }
}

onMounted(() => startup())

async function saveConfig() {
  const data = await api('/api/config', configBody())
  store.status.cfg = data.cfg
  applyStatusCfg()
  message.success('配置已保存')
}

async function savePathConfig() {
  await api('/api/config', pathConfigBody())
  store.status = await api('/api/status')
  applyStatusCfg()
  await loadSaves()
  message.success('存档路径已保存')
}

async function applySections(sections) {
  const names = namesOrCurrent()
  if (!names.length) throw new Error('没有存档')
  await api('/api/config', configBody())
  confirm(`将对 ${names.length} 个存档应用：${sections.join('、')}。`, async () => {
    await api('/api/apply', {
      names,
      sections,
      scope: store.scope,
      force: store.force,
    })
    await loadSaves()
    message.success('已应用')
  })
}

function diploRowPayload(row) {
  const e = row.edit
  const item = { fid: row.fid }
  if (e.relation != null && e.relation !== '') item.relation = e.relation
  if (e.friend != null) item.friend = e.friend
  if (e.armistice != null) item.armistice = e.armistice
  if (e.favour != null && e.favour !== '') item.favour = e.favour
  if (e.favour_other != null && e.favour_other !== '') item.favour_other = e.favour_other
  return item
}
</script>

<template>
        <n-layout style="height:100vh">
          <n-alert
            v-if="bootFailed"
            type="warning"
            closable
            style="margin:0;border-radius:0"
            @close="bootFailed = ''"
          >
            {{ bootFailed }}
            <template v-if="bootFailed.includes('8765') || bootFailed.includes('界面服务')">
              <br>
              <n-button size="tiny" quaternary type="primary" style="margin-top:6px" @click="startup">重试连接</n-button>
            </template>
          </n-alert>
          <n-layout-header bordered class="app-header" style="height:56px;padding:0 20px;display:flex;align-items:center;gap:14px">
            <n-text strong class="app-title">SUTK 修改器</n-text>
            <n-select
              v-model:value="store.current"
              :options="saveOptions"
              placeholder="选择存档"
              style="flex:1;max-width:480px"
              size="small"
            />
            <n-tag size="small" :type="store.status?.game_running ? 'warning' : 'default'" bordered>
              {{ store.status?.game_running ? '游戏运行中' : '游戏未运行' }}
            </n-tag>
            <n-tag size="small" :type="store.status?.cfg?.auto_apply ? 'success' : 'default'" bordered>
              {{ store.status?.cfg?.auto_apply ? '自动修改 开' : '自动修改 关' }}
            </n-tag>
            <n-tag size="small" :type="store.status?.admin ? 'success' : 'default'" bordered>
              {{ store.status?.admin ? '管理员' : '普通权限' }}
            </n-tag>
          </n-layout-header>
          <n-layout has-sider style="height:calc(100vh - 56px)">
            <n-layout-sider bordered class="app-sider" :width="148" :native-scrollbar="false">
              <n-menu
                :value="page"
                :options="menuOptions"
                :icon-size="18"
                @update:value="onPage"
              />
            </n-layout-sider>
            <n-layout-content class="app-content" content-style="padding:16px 20px 20px;display:flex;flex-direction:column;min-height:0">
              <n-spin
                class="main-spin"
                :show="store.loading"
                description="处理中…"
                :content-style="{ flex: '1', minHeight: 0, display: 'flex', flexDirection: 'column' }"
              >
                <SavesView v-if="page === 'saves'">
                  <template #actions>
                    <n-space vertical :size="12">
                      <n-space wrap :size="[10, 10]">
                        <n-button type="primary" @click="run(() => applySections(store.sections))">应用勾选</n-button>
                        <n-button @click="run(() => applySections(['tech']))">只满科技</n-button>
                        <n-button @click="run(() => applySections(['money']))">只满金钱</n-button>
                        <n-button @click="run(() => applySections(['conscript', 'food']))">兵役+粮食</n-button>
                        <n-button @click="run(() => applySections(['troop']))">只补兵力</n-button>
                      </n-space>
                      <n-space wrap :size="[10, 10]">
                        <n-button
                          type="error"
                          @click="
                            run(() => {
                              const names = namesOrCurrent()
                              if (!names.length) throw new Error('先勾选存档')
                              confirm(`恢复 ${names.length} 个存档的原始备份？`, async () => {
                                await api('/api/restore', { names })
                                await loadSaves()
                              })
                            })
                          "
                        >还原选中</n-button>
                        <n-button @click="run(saveConfig)">保存勾选和数值</n-button>
                        <n-button @click="run(loadSaves)">刷新存档</n-button>
                      </n-space>
                    </n-space>
                  </template>
                </SavesView>

                <GeneralsView
                  v-else-if="page === 'generals'"
                  @reload-extern="run(loadExtern)"
                  @write-one="
                    (row) =>
                      run(async () => {
                        await api('/api/generals/edit', {
                          name: store.current,
                          pid: row.pid,
                          values: row.edit,
                        })
                        await loadGenerals()
                      })
                  "
                  @write-extern="
                    (row) =>
                      run(async () => {
                        await api('/api/extern/edit', {
                          guid: row.guid,
                          kind: row.kind,
                          values: row.edit,
                        })
                        await loadExtern()
                      })
                  "
                >
                  <template #save-actions>
                    <n-button type="primary" @click="run(() => confirm('把本国在世武将六维全部改成目标值？', async () => {
                      await api('/api/generals/edit', { name: store.current, apply_targets: true })
                      await loadGenerals()
                    }))">全部改成目标值</n-button>
                    <n-button @click="run(loadGenerals)">刷新</n-button>
                  </template>
                </GeneralsView>

                <CitiesView v-else-if="page === 'cities'" ref="citiesRef">
                  <template #toolbar>
                    <n-button @click="run(loadCities)">刷新</n-button>
                    <n-button @click="run(() => api('/api/health?name=' + encodeURIComponent(store.current)))">健康检查</n-button>
                    <n-button @click="appendLog(store.cityProblems.length ? store.cityProblems : '没有一致性问题')">一致性问题</n-button>
                  </template>
                  <template #transfer>
                    <n-button
                      type="primary"
                      @click="
                        run(() => {
                          const keys = citiesRef?.checkedKeys?.value ?? citiesRef?.checkedKeys ?? []
                          if (!keys.length) throw new Error('先勾选城市')
                          confirm(
                            `把 ${keys.length} 座城交给目标势力？${store.allowEmpty ? '已允许零城。' : '被转空势力会留一座城。'}`,
                            async () => {
                              await api('/api/transfer', {
                                name: store.current,
                                keys,
                                target: store.cityTarget,
                                move_officers: store.moveOfficers,
                                keep_one: !store.allowEmpty,
                              })
                              await loadCities()
                            },
                          )
                        })
                      "
                    >转移选中的城</n-button>
                  </template>
                  <template #repair>
                    <n-button
                      type="error"
                      @click="
                        run(() =>
                          confirm('用对照档修城市归属？会先另存修复前备份。', async () => {
                            await api('/api/repair', { name: store.current, src: store.repairSrc })
                            await loadCities()
                          }),
                        )
                      "
                    >修复全吞并</n-button>
                  </template>
                </CitiesView>

                <DiploView
                  v-else-if="page === 'diplo'"
                  @write-one="
                    (row) =>
                      run(async () => {
                        await api('/api/diplo/write', {
                          name: store.current,
                          changes: [diploRowPayload(row)],
                        })
                        await loadDiplo()
                      })
                  "
                >
                  <template #toolbar>
                    <n-space wrap>
                      <n-button
                        v-for="m in [
                          ['relation', '关系全拉满'],
                          ['friend-on', '全部同盟'],
                          ['friend-off', '解除同盟'],
                          ['arm-on', '全部停战'],
                          ['arm-off', '解除停战'],
                          ['favour', '我方人情 20'],
                        ]"
                        :key="m[0]"
                        size="small"
                        @click="
                          run(() => {
                            const mode = m[0]
                            const changes = store.diplo.map((r) => {
                              if (mode === 'relation') return { fid: r.fid, relation: 100 }
                              if (mode === 'friend-on') return { fid: r.fid, friend: true }
                              if (mode === 'friend-off') return { fid: r.fid, friend: false }
                              if (mode === 'arm-on') return { fid: r.fid, armistice: true }
                              if (mode === 'arm-off') return { fid: r.fid, armistice: false }
                              return { fid: r.fid, favour: 20 }
                            })
                            confirm(`对 ${changes.length} 个势力执行批量修改？`, async () => {
                              await api('/api/diplo/write', { name: store.current, changes })
                              await loadDiplo()
                            })
                          })
                        "
                      >{{ m[1] }}</n-button>
                      <n-button size="small" @click="run(loadDiplo)">刷新</n-button>
                    </n-space>
                  </template>
                </DiploView>

                <CheckView v-else-if="page === 'check'">
                  <template #toolbar>
                    <n-space>
                      <n-button type="primary" @click="run(async () => { await loadAudit() })">存档体检</n-button>
                      <n-button @click="run(loadHistory)">刷新历史</n-button>
                    </n-space>
                  </template>
                  <template #undo="{ save, file }">
                    <n-button
                      size="tiny"
                      @click="
                        run(() =>
                          confirm(`回滚 ${save} 到该快照？`, async () => {
                            await api('/api/undo', { name: save, file })
                            await loadHistory()
                            await loadSaves()
                          }),
                        )
                      "
                    >回滚</n-button>
                  </template>
                </CheckView>

                <MemoryView v-else-if="page === 'memory'">
                  <template #scan>
                    <n-button type="primary" @click="run(async () => {
                      appendLog('正在扫描…')
                      const body = { name: store.current, field: store.memField }
                      if (store.memSeed.trim()) body.seed = store.memSeed.trim()
                      await api('/api/mem/scan', body)
                      await loadMem()
                    })">扫描</n-button>
                  </template>
                  <template #filter>
                    <n-button @click="run(async () => {
                      if (!store.memFilter.trim()) throw new Error('先填新数值')
                      await api('/api/mem/filter', { value: store.memFilter.trim() })
                      await loadMem()
                    })">过滤</n-button>
                  </template>
                  <template #write>
                    <n-button type="error" @click="run(async () => {
                      const hits = store.mem?.hits || 0
                      confirm(`写入剩余 ${hits} 处？`, async () => {
                        await api('/api/mem/write', { value: store.memWrite })
                        await loadMem()
                      })
                    })">写入</n-button>
                  </template>
                  <template #elevate>
                    <n-button @click="run(async () => {
                      await api('/api/elevate')
                      appendLog('等待提权…')
                      for (let i = 0; i < 30; i++) {
                        await new Promise((r) => setTimeout(r, 1000))
                        try {
                          store.status = await api('/api/status')
                          if (store.status.admin) { await loadMem(); appendLog('已提权'); return }
                        } catch { /* wait */ }
                      }
                      throw new Error('提权后未连上')
                    })">管理员重新打开</n-button>
                  </template>
                </MemoryView>

                <GuideView v-else-if="page === 'guide'" />

                <LogView v-else-if="page === 'log'" />

                <SettingsView v-else-if="page === 'settings'">
                  <template #path-actions>
                    <n-space wrap>
                      <n-button type="primary" @click="run(savePathConfig)">保存路径</n-button>
                      <n-button @click="run(() => api('/api/open-folder', { kind: 'saves' }))">打开存档文件夹</n-button>
                      <n-button @click="run(() => api('/api/open-folder', { kind: 'extern' }))">打开模板所在文件夹</n-button>
                    </n-space>
                  </template>
                  <template #run-actions>
                    <n-space>
                      <n-button type="primary" @click="run(saveConfig)">保存开关</n-button>
                      <n-button @click="run(() => api('/api/watcher'))">启动后台热键</n-button>
                    </n-space>
                  </template>
                  <template #orphan-actions>
                    <n-space>
                      <n-button @click="run(loadOrphans)">查看</n-button>
                      <n-button type="error" @click="run(() => confirm('移进回收站？', async () => {
                        await api('/api/cleanup')
                        await loadOrphans()
                      }))">清理</n-button>
                    </n-space>
                  </template>
                  <template #uninstall>
                    <n-button
                      type="error"
                      @click="
                        run(() => {
                          if (store.uninstallWord !== '卸载') throw new Error('请输入：卸载')
                          confirm('确认卸载并写回所有备份？', () => api('/api/uninstall'))
                        })
                      "
                    >卸载</n-button>
                  </template>
                </SettingsView>
              </n-spin>
            </n-layout-content>
          </n-layout>
        </n-layout>
</template>
