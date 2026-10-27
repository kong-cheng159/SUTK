<script setup>
import { computed, ref } from 'vue'
import { useMessage } from 'naive-ui'
import { store } from '../store'
import { isTauri, pickSaveFolder, pickExternSavFile } from '../tauriPick'

const message = useMessage()
const inTauri = isTauri()
const picking = ref(false)

async function browseSavesDir() {
  if (!inTauri) {
    message.info('纯浏览器调试请手输路径；请用 SUTK修改器.exe 打开后可浏览文件夹')
    return
  }
  picking.value = true
  try {
    const p = await pickSaveFolder(store.savesDir || store.status?.saves_dir)
    if (p) store.savesDir = p
  } catch (e) {
    message.error(e.message || '打开文件夹选择失败')
  } finally {
    picking.value = false
  }
}

async function browseExternFile() {
  if (!inTauri) {
    message.info('纯浏览器调试请手输路径；请用 SUTK修改器.exe 打开后可选择文件')
    return
  }
  picking.value = true
  try {
    const p = await pickExternSavFile(store.externPath || store.status?.extern_path)
    if (p) store.externPath = p
  } catch (e) {
    message.error(e.message || '打开文件选择失败')
  } finally {
    picking.value = false
  }
}

const DEFAULT_SAVES_HINT = '%LOCALAPPDATA%\\ProjectA\\Saved\\Saves'
const DEFAULT_EXTERN_HINT = '%LOCALAPPDATA%\\ProjectA\\Saved\\ExternPersonage.sav'

const usingDefault = computed(() => !store.savesDir.trim())
const effectiveSavesDir = computed(() => store.status?.saves_dir || '—')
/** 后端未重启时可能没有 saves_dir_default，用生效路径或占位说明 */
const defaultSavesDir = computed(() => {
  const fromApi = store.status?.saves_dir_default
  if (fromApi) return fromApi
  if (usingDefault.value && store.status?.saves_dir) return store.status.saves_dir
  return DEFAULT_SAVES_HINT
})
const defaultExtern = computed(() => {
  const fromApi = store.status?.extern_path_default
  if (fromApi) return fromApi
  if (!store.externPath.trim() && store.status?.extern_path) return store.status.extern_path
  return DEFAULT_EXTERN_HINT
})
const effectiveExtern = computed(() => store.status?.extern_path || '—')
const savesOk = computed(() => store.status?.saves_dir_ok !== false)
const saveCount = computed(() => store.status?.save_count ?? 0)
const showDefaultCompare = computed(
  () =>
    !usingDefault.value &&
    defaultSavesDir.value &&
    effectiveSavesDir.value !== '—' &&
    defaultSavesDir.value !== effectiveSavesDir.value,
)
</script>

<template>
  <n-scrollbar style="max-height:100%">
    <n-space vertical size="large">
      <n-card title="存档路径" size="small">
        <n-space vertical size="medium">
          <n-alert v-if="!savesOk" type="error" :bordered="false">
            当前存档目录不可用，请检查路径或改回默认。生效路径：{{ effectiveSavesDir }}
          </n-alert>
          <n-alert v-else-if="saveCount === 0" type="warning" :bordered="false">
            目录可读，但未发现 .sav 文件（共 {{ saveCount }} 个）。请确认游戏已存过档，或路径是否选对。
          </n-alert>
          <div>
            <n-text depth="3">
              {{ usingDefault ? '当前使用系统默认路径' : '当前生效（已自定义）' }}
            </n-text>
            <div class="path-line">{{ effectiveSavesDir }}</div>
            <template v-if="showDefaultCompare">
              <n-text depth="3">系统默认（恢复默认后将回到）</n-text>
              <div class="path-line muted">{{ defaultSavesDir }}</div>
            </template>
            <n-text v-else depth="3" class="default-hint">
              未自定义时，游戏存档一般在：
              <span class="mono">{{ defaultSavesDir }}</span>
            </n-text>
          </div>
          <n-form label-placement="top" size="small">
            <n-form-item label="自定义存档目录（留空 = 默认）">
              <n-input-group>
                <n-input
                  v-model:value="store.savesDir"
                  placeholder="例如 D:\Games\ProjectA\Saved\Saves"
                  clearable
                />
                <n-button :loading="picking" :type="inTauri ? 'primary' : 'default'" @click="browseSavesDir">
                  浏览文件夹
                </n-button>
              </n-input-group>
            </n-form-item>
            <n-form-item label="自建模板 ExternPersonage.sav（可选，留空自动推导）">
              <n-input-group>
                <n-input
                  v-model:value="store.externPath"
                  :placeholder="defaultExtern || '…\\Saved\\ExternPersonage.sav'"
                  clearable
                />
                <n-button :loading="picking" @click="browseExternFile">选择文件</n-button>
              </n-input-group>
            </n-form-item>
            <n-text depth="3" style="display:block;margin-top:-4px">
              生效中的模板：{{ effectiveExtern }}
            </n-text>
          </n-form>
          <n-space wrap>
            <slot name="path-actions" />
            <n-button quaternary @click="store.savesDir = ''; store.externPath = ''">
              恢复默认路径
            </n-button>
          </n-space>
          <p class="hint">
            路径保存在修改器配置里，换电脑或给别人用时可在设置里改。支持环境变量（如 %LOCALAPPDATA%）。
            {{ usingDefault ? '当前使用系统默认目录。' : '保存后会重新扫描存档列表。' }}
          </p>
        </n-space>
      </n-card>

      <n-card title="运行" size="small">
        <n-space vertical>
          <n-checkbox v-model:checked="store.setAuto">游戏启动时自动改档（默认关）</n-checkbox>
          <n-checkbox v-model:checked="store.setSnap">游戏自己存档时也在本地留快照（默认关）</n-checkbox>
          <slot name="run-actions" />
        </n-space>
        <p class="hint" style="margin-top:12px">热键仍由后台程序注册，呼出的是原来的控制台。</p>
      </n-card>
      <n-card title="已删除存档的本地副本" size="small">
        <pre style="margin:0 0 12px;white-space:pre-wrap;font-size:13px">{{ store.orphansText || '点「查看」列出待清理项。' }}</pre>
        <slot name="orphan-actions" />
      </n-card>
      <n-card title="安全卸载" size="small">
        <p class="hint">会把所有已有备份写回存档，并删掉开机启动项。输入「卸载」后执行。</p>
        <n-space>
          <n-input v-model:value="store.uninstallWord" placeholder="卸载" style="width:120px" />
          <slot name="uninstall" />
        </n-space>
      </n-card>
    </n-space>
  </n-scrollbar>
</template>

<style scoped>
.path-line {
  font-family: Consolas, 'Microsoft YaHei UI', monospace;
  font-size: 12px;
  word-break: break-all;
  margin: 4px 0 10px;
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--app-surface-muted, #f8fafc);
  border: 1px solid var(--app-border, #e2e8f0);
}

.path-line.muted {
  opacity: 0.85;
}

.default-hint {
  display: block;
  margin-top: 8px;
  line-height: 1.55;
}

.default-hint .mono {
  font-family: Consolas, 'Microsoft YaHei UI', monospace;
  font-size: 12px;
  word-break: break-all;
}
</style>
