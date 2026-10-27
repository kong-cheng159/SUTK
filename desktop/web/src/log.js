import { ref } from 'vue'

export const logText = ref('')

export function appendLog(lines) {
  const text = (Array.isArray(lines) ? lines : [String(lines)]).filter(Boolean).join('\n')
  if (!text) return
  logText.value += (logText.value ? '\n' : '') + text + '\n'
}

export function clearLog() {
  logText.value = ''
}
