// Client for the chat agent (ADR-014).
//
// On AWS the agent runs on Amazon Bedrock AgentCore Runtime. The browser calls its HTTPS
// endpoint directly with the same Cognito access token it sends to the REST API; AgentCore
// verifies the token before the agent code runs. The reply is a Server-Sent Events stream:
// one `data: {json}` line per event (see agent/finance_agent/chat.py for the vocabulary).
import { authEnabled, getAccessToken } from './auth'
import { getReceipt, requestReceiptUpload, uploadToS3 } from './api'

const AGENT_URL = import.meta.env.VITE_AGENT_URL || ''
const SESSION_HEADER = 'X-Amzn-Bedrock-AgentCore-Runtime-Session-Id'

export const chatEnabled = Boolean(AGENT_URL)

// AgentCore requires session ids of at least 33 characters; a UUID has 36. One id = one
// conversation: the runtime keeps a separate microVM (and the agent its history) per id.
export const newSessionId = () => crypto.randomUUID()

// Sends one user message and calls onEvent for every event of the streamed reply.
// Rejects on network or HTTP errors; `signal` aborts the stream.
export async function streamChat({ prompt, sessionId, onEvent, signal }) {
  const headers = { 'Content-Type': 'application/json', [SESSION_HEADER]: sessionId }
  if (authEnabled) {
    const token = await getAccessToken()
    if (!token) throw new Error('Сесія завершилась. Увійдіть знову.')
    headers.Authorization = `Bearer ${token}`
  }

  const response = await fetch(AGENT_URL, {
    method: 'POST',
    headers,
    body: JSON.stringify({ prompt }),
    signal,
  })
  if (response.status === 401 || response.status === 403) {
    throw new Error('Сесія завершилась. Увійдіть знову.')
  }
  if (!response.ok || !response.body) {
    throw new Error(`Чат недоступний (HTTP ${response.status}).`)
  }

  // SSE: events are separated by a blank line and may arrive split across chunks.
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  const flush = (chunk) => {
    for (const line of chunk.split('\n')) {
      if (!line.startsWith('data:')) continue
      let event
      try {
        event = JSON.parse(line.slice(5).trim())
      } catch {
        continue
      }
      // Errors raised inside the runtime's own wrapper have no `type`.
      if (event && !event.type && event.error) event = { type: 'error', message: null }
      if (event?.type) onEvent(event)
    }
  }
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop()
    parts.forEach(flush)
  }
  if (buffer.trim()) flush(buffer)
}

// --- Receipt photo in chat ------------------------------------------------------------------
// Same pipeline as the Upload page (ADR-010, ADR-013): presigned POST straight to S3, then poll
// until the parse Lambda is done. The agent never sees the image; it reads the draft by id.
const EXTENSION_MIME_TYPES = {
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  png: 'image/png',
  heic: 'image/heic',
  heif: 'image/heif',
}
const POLL_INTERVAL_MS = 2000
const POLL_TIMEOUT_MS = 120000
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

export async function uploadReceiptAndWait(file) {
  const extension = file.name.split('.').pop()?.toLowerCase()
  const contentType = file.type || EXTENSION_MIME_TYPES[extension]
  if (!Object.values(EXTENSION_MIME_TYPES).includes(contentType)) {
    throw new Error('Підтримуються лише файли JPEG, PNG, HEIC або HEIF.')
  }
  const upload = await requestReceiptUpload(contentType)
  await uploadToS3(upload, file)

  const deadline = Date.now() + POLL_TIMEOUT_MS
  let receipt = await getReceipt(upload.receipt_id)
  while (receipt.status === 'UPLOADING') {
    if (Date.now() > deadline) throw new Error('Розпізнавання триває занадто довго. Спробуйте пізніше.')
    await sleep(POLL_INTERVAL_MS)
    receipt = await getReceipt(upload.receipt_id)
  }
  if (receipt.status === 'FAILED') throw new Error(receipt.error || 'Не вдалося розпізнати чек.')
  return upload.receipt_id
}
