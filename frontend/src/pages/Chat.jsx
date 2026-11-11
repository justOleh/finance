import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bot, CheckCircle2, Paperclip, Plus, RotateCcw, Save, Send, Trash2, XCircle } from 'lucide-react'
import { createExpense } from '../api'
import { chatEnabled, newSessionId, streamChat, uploadReceiptAndWait } from '../chatApi'

const TOOL_LABELS = {
  list_expenses: 'Шукаю витрати…',
  spending_summary: 'Рахую суми…',
  get_expense: 'Відкриваю витрату…',
  get_receipt_draft: 'Читаю чек…',
  propose_expense: 'Готую чернетку…',
}

const SUGGESTIONS = [
  'Скільки я витратив цього місяця?',
  'У яких магазинах я витратив найбільше минулого місяця?',
  'Додай 250 грн у кавʼярні сьогодні',
]

const toNumber = (value) => {
  const num = Number(value)
  return Number.isFinite(num) ? num : 0
}

let nextId = 0
const localId = () => `m${++nextId}`

export default function Chat() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState(null)
  const sessionRef = useRef(newSessionId())
  const abortRef = useRef(null)
  const bottomRef = useRef(null)
  const fileRef = useRef(null)

  useEffect(() => () => abortRef.current?.abort(), [])
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, status])

  const patchMessage = (id, patch) =>
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, ...patch(m) } : m)))

  const patchDraft = (messageId, draftId, patch) =>
    patchMessage(messageId, (m) => ({
      drafts: m.drafts.map((d) => (d.id === draftId ? { ...d, ...patch(d) } : d)),
    }))

  // `shown` is what appears in the user's bubble; `prompt` is what the agent receives.
  const send = async (prompt, shown = prompt) => {
    const replyId = localId()
    setMessages((prev) => [
      ...prev,
      { id: localId(), role: 'user', text: shown },
      { id: replyId, role: 'assistant', text: '', drafts: [], error: null },
    ])
    setBusy(true)
    setStatus('Думаю…')
    const controller = new AbortController()
    abortRef.current = controller

    try {
      await streamChat({
        prompt,
        sessionId: sessionRef.current,
        signal: controller.signal,
        onEvent: (event) => {
          if (event.type === 'text') {
            setStatus(null)
            patchMessage(replyId, (m) => ({ text: m.text + event.text }))
          } else if (event.type === 'tool') {
            setStatus(TOOL_LABELS[event.name] || 'Працюю…')
          } else if (event.type === 'draft') {
            const draft = {
              ...event.draft,
              total: toNumber(event.draft.total).toFixed(2),
              notes: event.draft.notes || '',
              items: (event.draft.items || []).map((i) => ({
                name: i.name,
                price: toNumber(i.price).toFixed(2),
              })),
              state: 'open',
              error: null,
            }
            patchMessage(replyId, (m) => ({ drafts: [...m.drafts, draft] }))
          } else if (event.type === 'error') {
            patchMessage(replyId, () => ({
              error: event.message || 'Сталася помилка. Спробуйте ще раз.',
            }))
          }
        },
      })
    } catch (err) {
      if (err.name !== 'AbortError') {
        // The chat is an extra door to the same data: when it fails, the pages still work.
        patchMessage(replyId, () => ({ error: err.message || 'Чат недоступний.' }))
      }
    } finally {
      setBusy(false)
      setStatus(null)
    }
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    const prompt = input.trim()
    if (!prompt || busy) return
    setInput('')
    send(prompt)
  }

  const handleFile = async (file) => {
    if (!file || busy) return
    setBusy(true)
    setStatus('Завантажую та розпізнаю чек…')
    try {
      const receiptId = await uploadReceiptAndWait(file)
      await send(
        `I uploaded a receipt photo. Its receipt id is ${receiptId}. Read the draft and prepare the expense for me to review.`,
        `📎 ${file.name}`,
      )
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { id: localId(), role: 'user', text: `📎 ${file.name}` },
        {
          id: localId(),
          role: 'assistant',
          text: '',
          drafts: [],
          error: err.response?.data?.detail || err.message,
        },
      ])
      setBusy(false)
      setStatus(null)
    }
  }

  // The agent cannot write. Saving happens here, on the user's click, through the same
  // POST /expenses as the other pages. The idempotency key makes a double click or a retry
  // return the first expense instead of creating a second one.
  const saveDraft = async (messageId, draft) => {
    if (!draft.store.trim()) {
      patchDraft(messageId, draft.id, () => ({ error: 'Вкажіть назву магазину.' }))
      return
    }
    patchDraft(messageId, draft.id, () => ({ state: 'saving', error: null }))
    try {
      await createExpense(
        {
          date: draft.date,
          store: draft.store.trim(),
          total: toNumber(draft.total),
          notes: draft.notes.trim() || null,
          items: draft.items
            .filter((i) => i.name.trim())
            .map((i) => ({ name: i.name.trim(), price: toNumber(i.price) })),
        },
        `chat-${draft.id}`,
      )
      patchDraft(messageId, draft.id, () => ({ state: 'saved' }))
    } catch (err) {
      const detail = err.response?.data?.detail
      patchDraft(messageId, draft.id, () => ({
        state: 'open',
        error: typeof detail === 'string' ? detail : err.message,
      }))
    }
  }

  const newChat = () => {
    abortRef.current?.abort()
    sessionRef.current = newSessionId()
    setMessages([])
    setBusy(false)
    setStatus(null)
  }

  if (!chatEnabled) {
    return (
      <div className="max-w-2xl">
        <h1 className="text-xl sm:text-2xl font-bold text-white mb-2">Чат</h1>
        <div className="card p-6 text-slate-400 text-sm">
          Чат не налаштовано для цього середовища (немає <code>VITE_AGENT_URL</code>). Усі дані
          доступні на інших сторінках.
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-3xl flex flex-col h-[calc(100dvh-7.5rem)] md:h-[calc(100dvh-3rem)]">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-white">Чат</h1>
          <p className="text-slate-400 text-sm mt-0.5">
            Запитайте про свої витрати або додайте нову. Зберігаєте завжди ви.
          </p>
        </div>
        <button type="button" onClick={newChat} className="btn-secondary text-xs py-2 px-3" title="Новий чат">
          <RotateCcw size={14} /> Новий
        </button>
      </div>

      <div className="flex-1 overflow-y-auto space-y-3 pr-1">
        {messages.length === 0 && (
          <div className="card p-6 space-y-3">
            <div className="flex items-center gap-2 text-slate-300 text-sm">
              <Bot size={18} className="text-brand-400" /> Спробуйте, наприклад:
            </div>
            <div className="flex flex-wrap gap-2">
              {SUGGESTIONS.map((s) => (
                <button key={s} type="button" className="btn-secondary text-xs py-2 px-3" onClick={() => send(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m) =>
          m.role === 'user' ? (
            <div key={m.id} className="flex justify-end">
              <div className="max-w-[85%] bg-brand-600 text-white rounded-2xl rounded-br-md px-4 py-2 text-sm whitespace-pre-wrap">
                {m.text}
              </div>
            </div>
          ) : (
            <div key={m.id} className="space-y-2">
              {m.text && (
                <div className="max-w-[85%] bg-slate-800 text-slate-100 rounded-2xl rounded-bl-md px-4 py-2 text-sm whitespace-pre-wrap">
                  {m.text}
                </div>
              )}
              {m.drafts.map((d) => (
                <DraftCard
                  key={d.id}
                  draft={d}
                  onChange={(patch) => patchDraft(m.id, d.id, () => patch)}
                  onSave={() => saveDraft(m.id, d)}
                  onCancel={() => patchDraft(m.id, d.id, () => ({ state: 'cancelled' }))}
                />
              ))}
              {m.error && (
                <div className="max-w-[85%] flex items-start gap-2 text-red-400 text-sm bg-red-900/20 border border-red-800/30 rounded-xl px-4 py-3">
                  <XCircle size={16} className="mt-0.5 shrink-0" />
                  <span>
                    {m.error} Дані доступні на <Link to="/dashboard" className="underline">панелі</Link>.
                  </span>
                </div>
              )}
            </div>
          ),
        )}

        {status && (
          <div className="flex items-center gap-2 text-slate-400 text-sm px-1">
            <span className="w-3 h-3 border-2 border-slate-400 border-t-transparent rounded-full animate-spin" />
            {status}
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2 pt-3">
        <input
          ref={fileRef}
          type="file"
          accept="image/jpeg,image/jpg,image/png,image/heic,image/heif,.heic,.heif"
          className="hidden"
          onChange={(e) => {
            handleFile(e.target.files[0])
            e.target.value = ''
          }}
        />
        <button
          type="button"
          className="btn-secondary px-3"
          disabled={busy}
          onClick={() => fileRef.current?.click()}
          title="Додати фото чека"
          aria-label="Додати фото чека"
        >
          <Paperclip size={16} />
        </button>
        <input
          className="input flex-1"
          placeholder="Напишіть повідомлення…"
          value={input}
          maxLength={2000}
          onChange={(e) => setInput(e.target.value)}
        />
        <button type="submit" className="btn-primary px-4" disabled={busy || !input.trim()} aria-label="Надіслати">
          <Send size={16} />
        </button>
      </form>
    </div>
  )
}

// The human-in-the-loop step: an editable draft that becomes an expense only on Save.
function DraftCard({ draft, onChange, onSave, onCancel }) {
  if (draft.state === 'saved') {
    return (
      <div className="max-w-[85%] flex items-center gap-2 text-green-400 text-sm bg-green-900/20 border border-green-800/30 rounded-xl px-4 py-3">
        <CheckCircle2 size={16} /> Збережено: {draft.store}, {toNumber(draft.total).toFixed(2)} грн
      </div>
    )
  }
  if (draft.state === 'cancelled') {
    return <div className="text-slate-500 text-sm px-1">Чернетку скасовано.</div>
  }

  const saving = draft.state === 'saving'
  const setField = (field) => (e) => onChange({ [field]: e.target.value })
  const setItem = (idx, field) => (e) =>
    onChange({ items: draft.items.map((it, i) => (i === idx ? { ...it, [field]: e.target.value } : it)) })

  return (
    <div className="card p-4 space-y-3 max-w-xl">
      <div>
        <p className="font-semibold text-white text-sm">Нова витрата: перевірте перед збереженням</p>
        <p className="text-slate-400 text-xs">Нічого не збережено, доки ви не натиснете "Зберегти".</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label className="label">Магазин</label>
          <input className="input" value={draft.store} onChange={setField('store')} />
        </div>
        <div>
          <label className="label">Дата</label>
          <input type="date" className="input" value={draft.date} onChange={setField('date')} />
        </div>
        <div>
          <label className="label">Сума (грн)</label>
          <input type="number" min="0" step="0.01" className="input" value={draft.total} onChange={setField('total')} />
        </div>
        <div>
          <label className="label">Нотатки</label>
          <input className="input" value={draft.notes} onChange={setField('notes')} />
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <p className="label">Позиції</p>
          <button
            type="button"
            className="btn-secondary text-xs py-1 px-2"
            onClick={() => onChange({ items: [...draft.items, { name: '', price: '0.00' }] })}
          >
            <Plus size={12} /> Додати
          </button>
        </div>
        {draft.items.map((item, idx) => (
          <div key={idx} className="flex gap-2 items-center">
            <input className="input flex-1" placeholder="Назва" value={item.name} onChange={setItem(idx, 'name')} />
            <input
              type="number"
              min="0"
              step="0.01"
              className="input w-24 sm:w-28"
              placeholder="Ціна"
              value={item.price}
              onChange={setItem(idx, 'price')}
            />
            <button
              type="button"
              className="btn-danger px-2 py-2"
              onClick={() => onChange({ items: draft.items.filter((_, i) => i !== idx) })}
              aria-label="Видалити позицію"
            >
              <Trash2 size={13} />
            </button>
          </div>
        ))}
      </div>

      {draft.error && (
        <div className="flex items-center gap-2 text-red-400 text-sm">
          <XCircle size={14} /> {draft.error}
        </div>
      )}

      <div className="flex gap-2">
        <button type="button" onClick={onSave} disabled={saving} className="btn-primary flex-1 justify-center py-2">
          <Save size={14} /> {saving ? 'Збереження…' : 'Зберегти'}
        </button>
        <button type="button" onClick={onCancel} disabled={saving} className="btn-secondary px-4">
          Скасувати
        </button>
      </div>
    </div>
  )
}
