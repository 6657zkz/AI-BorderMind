// POST 型 SSE：用 fetch 读流（EventSource 只支持 GET）
export async function streamChat(payload, handlers, { signal, onActivity } = {}) {
  const res = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  })
  if (!res.ok || !res.body) {
    throw new Error(`SSE 连接失败: ${res.status}`)
  }
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let receivedDone = false
  let receivedTerminal = false

  const emit = (chunk) => {
    const parsed = parseEvent(chunk)
    if (!parsed) return
    if (['result', 'clarification', 'error'].includes(parsed.event)) receivedTerminal = true
    if (parsed.event === 'done') receivedDone = true
    if (handlers[parsed.event]) handlers[parsed.event](parsed.data)
  }

  try {
    while (!receivedDone) {
      const { value, done } = await reader.read()
      if (done) break
      onActivity?.()
      buffer += decoder.decode(value, { stream: true })
      let idx
      while (!receivedDone && (idx = buffer.search(/\r?\n\r?\n/)) !== -1) {
        const separator = buffer.match(/\r?\n\r?\n/)?.[0] || '\n\n'
        const chunk = buffer.slice(0, idx)
        buffer = buffer.slice(idx + separator.length)
        emit(chunk)
      }
    }
    if (!receivedDone && buffer.trim()) emit(buffer)
    if (!receivedDone || !receivedTerminal) throw new Error('流式响应未返回最终结果')
  } finally {
    try {
      await reader.cancel()
    } catch {
      // 请求已关闭时 reader.cancel() 会失败，无需额外处理。
    }
    reader.releaseLock()
  }
}

function parseEvent(chunk) {
  let event = 'message'
  const dataLines = []
  for (const line of chunk.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
  }
  if (!dataLines.length) return null
  let data = dataLines.join('\n')
  try {
    data = JSON.parse(data)
  } catch {
    /* keep raw string */
  }
  return { event, data }
}
