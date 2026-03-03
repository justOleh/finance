import { useState, useRef } from 'react'
import { Upload, ImageIcon, CheckCircle2, XCircle, Trash2, Plus, Save } from 'lucide-react'
import { parseReceipt, createExpense } from '../api'
import { format } from 'date-fns'
import { uk } from 'date-fns/locale'

const ALLOWED_IMAGE_MIME_TYPES = new Set([
  'image/jpeg',
  'image/png',
  'image/jpg',
  'image/heic',
  'image/heif',
])

const ALLOWED_IMAGE_EXTENSIONS = new Set(['.jpg', '.jpeg', '.png', '.heic', '.heif'])

const getFileExtension = (filename) => {
  if (!filename) return ''
  const dotIndex = filename.lastIndexOf('.')
  return dotIndex >= 0 ? filename.slice(dotIndex).toLowerCase() : ''
}

const isHeicFile = (f) => {
  const ext = getFileExtension(f?.name)
  return f?.type === 'image/heic' || f?.type === 'image/heif' || ext === '.heic' || ext === '.heif'
}

const isAllowedImageFile = (f) => {
  const ext = getFileExtension(f?.name)
  return ALLOWED_IMAGE_MIME_TYPES.has(f?.type) || ALLOWED_IMAGE_EXTENSIONS.has(ext)
}

const toNumber = (value) => {
  const num = Number(value)
  return Number.isFinite(num) ? num : 0
}

const formatDateSafe = (value) => {
  if (!value) return '—'
  const parsedDate = new Date(value)
  if (Number.isNaN(parsedDate.getTime())) return '—'
  return format(parsedDate, 'd MMM yyyy', { locale: uk })
}

const getItemAmount = (item) => toNumber(item?.price ?? item?.item_price)
const formatCurrencyUAH = (value) => new Intl.NumberFormat('uk-UA', {
  style: 'currency',
  currency: 'UAH',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
}).format(toNumber(value))

export default function UploadReceipt() {
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [result, setResult] = useState(null)
  const [draft, setDraft] = useState(null)
  const [error, setError] = useState(null)
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef(null)

  const handleFile = (f) => {
    if (!f) return
    if (!isAllowedImageFile(f)) {
      setError('Підтримуються лише файли JPEG, PNG, HEIC або HEIF.')
      return
    }
    setFile(f)
    setError(null)
    setResult(null)
    setDraft(null)
    if (isHeicFile(f)) {
      setPreview(null)
      return
    }
    const reader = new FileReader()
    reader.onload = (e) => setPreview(e.target.result)
    reader.readAsDataURL(f)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    handleFile(e.dataTransfer.files[0])
  }

  const handleUpload = async () => {
    if (!file) return
    setUploading(true)
    setError(null)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const data = await parseReceipt(fd)
      setDraft({
        date: data.date,
        store: data.store || '',
        total: toNumber(data.total).toFixed(2),
        notes: data.notes || '',
        receipt_image_path: data.receipt_image_path || null,
        items: Array.isArray(data.items)
          ? data.items.map((item) => ({
            name: item?.name || '',
            price: toNumber(item?.price ?? item?.item_price).toFixed(2),
          }))
          : [],
      })
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
    } finally {
      setUploading(false)
    }
  }

  const setDraftField = (field) => (e) => {
    const value = e.target.value
    setDraft((prev) => ({ ...prev, [field]: value }))
  }

  const setDraftItem = (idx, field) => (e) => {
    const value = e.target.value
    setDraft((prev) => ({
      ...prev,
      items: prev.items.map((item, index) => (index === idx ? { ...item, [field]: value } : item)),
    }))
  }

  const addDraftItem = () => {
    setDraft((prev) => ({ ...prev, items: [...(prev.items || []), { name: '', price: '0.00' }] }))
  }

  const deleteDraftItem = (idx) => {
    setDraft((prev) => ({
      ...prev,
      items: prev.items.filter((_, index) => index !== idx),
    }))
  }

  const recalcTotal = () => {
    setDraft((prev) => {
      const total = (prev.items || []).reduce((sum, item) => sum + toNumber(item.price), 0)
      return { ...prev, total: total.toFixed(2) }
    })
  }

  const handleSave = async () => {
    if (!draft) return
    if (!draft.store?.trim()) {
      setError('Вкажіть назву магазину перед збереженням.')
      return
    }

    setSaving(true)
    setError(null)
    try {
      const payload = {
        date: draft.date,
        store: draft.store.trim(),
        total: toNumber(draft.total),
        notes: draft.notes?.trim() || null,
        receipt_image_path: draft.receipt_image_path || null,
        items: (draft.items || [])
          .filter((item) => item.name?.trim())
          .map((item) => ({
            name: item.name.trim(),
            price: toNumber(item.price),
          })),
      }

      const saved = await createExpense(payload)
      setResult(saved)
      setDraft(null)
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
    } finally {
      setSaving(false)
    }
  }

  const reset = () => {
    setFile(null)
    setPreview(null)
    setResult(null)
    setDraft(null)
    setError(null)
  }

  return (
    <div className="max-w-2xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">Завантажити чек</h1>
        <p className="text-slate-400 text-sm mt-0.5">
          Завантажте фото, і ми автоматично витягнемо дані
        </p>
      </div>

      {!result && !draft ? (
        <div className="space-y-4">
          {/* Drop zone */}
          <div
            className={`card p-8 border-2 border-dashed text-center cursor-pointer transition-all duration-150
              ${dragging ? 'border-brand-500 bg-brand-500/5' : 'border-slate-700 hover:border-slate-600'}`}
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
          >
            <input
              ref={inputRef}
              type="file"
              accept="image/jpeg,image/jpg,image/png,image/heic,image/heif,.heic,.heif"
              className="hidden"
              onChange={(e) => handleFile(e.target.files[0])}
            />
            {preview ? (
              <div className="space-y-3">
                <img
                  src={preview}
                  alt="Попередній перегляд чека"
                  className="max-h-64 mx-auto rounded-xl object-contain shadow-xl"
                />
                <p className="text-slate-400 text-sm">{file.name}</p>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-3 py-4">
                <div className="w-16 h-16 rounded-2xl bg-slate-800 flex items-center justify-center">
                  <ImageIcon size={32} className="text-slate-500" />
                </div>
                <div>
                  <p className="text-white font-medium">Перетягніть чек сюди</p>
                  <p className="text-slate-500 text-sm mt-0.5">або натисніть для вибору · JPEG, PNG, HEIC</p>
                </div>
              </div>
            )}
          </div>

          {error && (
            <div className="flex items-center gap-2 text-red-400 text-sm bg-red-900/20 border border-red-800/30 rounded-xl px-4 py-3">
              <XCircle size={16} />
              {error}
            </div>
          )}

          <div className="flex gap-3">
            <button
              onClick={handleUpload}
              disabled={!file || uploading}
              className="btn-primary flex-1 justify-center py-3"
            >
              {uploading ? (
                <>
                  <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Розпізнаємо чек…
                </>
              ) : (
                <>
                  <Upload size={16} />
                  Розпізнати чек
                </>
              )}
            </button>
            {file && (
              <button onClick={reset} className="btn-secondary px-4">
                Очистити
              </button>
            )}
          </div>
        </div>
      ) : draft ? (
        <div className="space-y-4">
          <div className="card p-6 space-y-4">
            <div>
              <p className="font-semibold text-white">Перевірте та відредагуйте розпізнавання</p>
              <p className="text-slate-400 text-sm">Дані буде збережено в базу тільки після натискання кнопки "Зберегти".</p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Магазин</label>
                <input className="input" value={draft.store} onChange={setDraftField('store')} />
              </div>
              <div>
                <label className="label">Дата</label>
                <input type="date" className="input" value={draft.date || ''} onChange={setDraftField('date')} />
              </div>
              <div>
                <label className="label">Сума (грн)</label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  className="input"
                  value={draft.total}
                  onChange={setDraftField('total')}
                />
              </div>
              <div>
                <label className="label">Нотатки</label>
                <input className="input" value={draft.notes} onChange={setDraftField('notes')} />
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <p className="label">Позиції</p>
                <div className="flex gap-2">
                  <button type="button" onClick={recalcTotal} className="btn-secondary text-xs py-1 px-2">
                    Перерахувати суму
                  </button>
                  <button type="button" onClick={addDraftItem} className="btn-secondary text-xs py-1 px-2">
                    <Plus size={12} /> Додати
                  </button>
                </div>
              </div>
              <div className="space-y-2">
                {(draft.items || []).length === 0 ? (
                  <p className="text-slate-500 text-sm">Позицій не знайдено</p>
                ) : (
                  draft.items.map((item, idx) => (
                    <div key={idx} className="flex gap-2 items-center">
                      <input
                        className="input flex-1"
                        placeholder="Назва"
                        value={item.name}
                        onChange={setDraftItem(idx, 'name')}
                      />
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        className="input w-32"
                        placeholder="Ціна"
                        value={item.price}
                        onChange={setDraftItem(idx, 'price')}
                      />
                      <button
                        type="button"
                        className="btn-danger px-2 py-2"
                        onClick={() => deleteDraftItem(idx)}
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>

            {error && (
              <div className="flex items-center gap-2 text-red-400 text-sm bg-red-900/20 border border-red-800/30 rounded-xl px-4 py-3">
                <XCircle size={16} />
                {error}
              </div>
            )}

            <div className="flex gap-3">
              <button onClick={handleSave} disabled={saving} className="btn-primary flex-1 justify-center py-3">
                {saving ? (
                  <>
                    <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Збереження…
                  </>
                ) : (
                  <>
                    <Save size={16} />
                    Зберегти в базу
                  </>
                )}
              </button>
              <button onClick={reset} className="btn-secondary px-4">Видалити</button>
            </div>
          </div>
        </div>
      ) : (
        /* ── Success result ──────────────────────────────────────────────── */
        <div className="space-y-4">
          <div className="card p-6 space-y-4">
            <div className="flex items-center gap-3">
              <CheckCircle2 size={28} className="text-green-400" />
              <div>
                <p className="font-semibold text-white">Чек успішно розпізнано!</p>
                <p className="text-slate-400 text-sm">Витрату збережено до ваших записів.</p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 pt-2">
              <InfoField label="Магазин" value={result.store} />
              <InfoField label="Сума" value={formatCurrencyUAH(result.total)} />
              <InfoField label="Дата" value={formatDateSafe(result.date)} />
              <InfoField label="ID витрати" value={`#${result.id}`} />
            </div>

            {result.items?.length > 0 && (
              <div>
                <p className="label mt-2">Розпізнані позиції</p>
                <div className="bg-slate-800 rounded-xl overflow-hidden">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-700">
                        <th className="px-4 py-2.5 text-left text-slate-400 font-medium">Позиція</th>
                        <th className="px-4 py-2.5 text-right text-slate-400 font-medium">Ціна</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.items.map((item, i) => (
                        <tr key={i} className="border-b border-slate-700/50">
                          <td className="px-4 py-2 text-slate-300">{item.name}</td>
                          <td className="px-4 py-2 text-right text-brand-400 font-medium">
                            {formatCurrencyUAH(getItemAmount(item))}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {result.notes && (
              <div>
                <p className="label">Сирий OCR-текст</p>
                <pre className="bg-slate-800 rounded-xl p-4 text-xs text-slate-400 whitespace-pre-wrap max-h-40 overflow-y-auto">
                  {result.notes}
                </pre>
              </div>
            )}
          </div>

          <button onClick={reset} className="btn-secondary w-full justify-center py-3">
            Завантажити інший чек
          </button>
        </div>
      )}
    </div>
  )
}

function InfoField({ label, value }) {
  return (
    <div className="bg-slate-800 rounded-xl p-3">
      <p className="text-xs text-slate-400 mb-0.5">{label}</p>
      <p className="font-semibold text-white">{value}</p>
    </div>
  )
}
