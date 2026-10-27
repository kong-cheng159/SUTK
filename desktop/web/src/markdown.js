function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, (ch) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]),
  )
}

function mdInline(text) {
  let s = esc(text)
  s = s.replace(/`([^`]+)`/g, '<code>$1</code>')
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  return s
}

function mdBlockStart(line) {
  return (
    /^```/.test(line) ||
    /^\|/.test(line) ||
    /^#{1,4}\s/.test(line) ||
    /^>\s?/.test(line) ||
    /^[-*]\s+/.test(line) ||
    /^\d+\.\s+/.test(line) ||
    /^---+$/.test(line.trim())
  )
}

function mdTable(rows) {
  const cells = (row) =>
    row
      .trim()
      .replace(/^\|/, '')
      .replace(/\|$/, '')
      .split('|')
      .map((c) => c.trim())
  const head = cells(rows[0])
  let start = 1
  if (rows[1] && /^\|?\s*:?-{3,}/.test(rows[1])) start = 2
  let html =
    '<div class="md-table"><table><thead><tr>' +
    head.map((c) => `<th>${mdInline(c)}</th>`).join('') +
    '</tr></thead><tbody>'
  for (let i = start; i < rows.length; i++) {
    const row = cells(rows[i])
    html +=
      '<tr>' + head.map((_, j) => `<td>${mdInline(row[j] || '')}</td>`).join('') + '</tr>'
  }
  return html + '</tbody></table></div>'
}

export function renderMarkdown(src) {
  const lines = String(src || '').replace(/\r\n/g, '\n').split('\n')
  let html = ''
  let i = 0
  while (i < lines.length) {
    const line = lines[i]
    if (!line.trim()) {
      i++
      continue
    }
    if (/^```/.test(line)) {
      const buf = []
      i++
      while (i < lines.length && !/^```/.test(lines[i])) buf.push(lines[i++])
      if (i < lines.length) i++
      html += `<pre><code>${esc(buf.join('\n'))}</code></pre>`
      continue
    }
    if (/^\|/.test(line)) {
      const rows = []
      while (i < lines.length && /^\|/.test(lines[i])) rows.push(lines[i++])
      html += mdTable(rows)
      continue
    }
    if (/^---+$/.test(line.trim())) {
      html += '<hr>'
      i++
      continue
    }
    const heading = /^(#{1,4})\s+(.*)$/.exec(line)
    if (heading) {
      html += `<h${heading[1].length}>${mdInline(heading[2])}</h${heading[1].length}>`
      i++
      continue
    }
    if (/^>\s?/.test(line)) {
      const buf = []
      while (i < lines.length && /^>\s?/.test(lines[i])) buf.push(lines[i++].replace(/^>\s?/, ''))
      html += `<blockquote>${buf.map(mdInline).join('<br>')}</blockquote>`
      continue
    }
    if (/^[-*]\s+/.test(line)) {
      const buf = []
      while (i < lines.length && /^[-*]\s+/.test(lines[i])) buf.push(lines[i++].replace(/^[-*]\s+/, ''))
      html += '<ul>' + buf.map((t) => `<li>${mdInline(t)}</li>`).join('') + '</ul>'
      continue
    }
    if (/^\d+\.\s+/.test(line)) {
      const buf = []
      while (i < lines.length && /^\d+\.\s+/.test(lines[i])) buf.push(lines[i++].replace(/^\d+\.\s+/, ''))
      html += '<ol>' + buf.map((t) => `<li>${mdInline(t)}</li>`).join('') + '</ol>'
      continue
    }
    const buf = [line]
    i++
    while (i < lines.length && lines[i].trim() && !mdBlockStart(lines[i])) buf.push(lines[i++])
    html += `<p>${buf.map(mdInline).join('<br>')}</p>`
  }
  return html
}
