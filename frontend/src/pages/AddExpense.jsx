import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Minus, Save, CheckCircle2 } from 'lucide-react'
import { createExpense } from '../api'

const today = () => new Date().toISOString().slice(0, 10)

export default function AddExpense() {
  const navigate = useNavigate()
  const [form, setForm] = useState({
    date: today(),
    store: '',
    total: '',
    notes: '',
  })
  const [items, setItems] = useState([{ name: '', price: '' }])
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState(null)

  const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }))

  const addItem = () => setItems((i) => [...i, { name: '', price: '' }])
  const removeItem = (idx) =>
    setItems((i) => (i.length > 1 ? i.filter((_, n) => n !== idx) : i))
  const setItem = (idx, field) => (e) =>
    setItems((arr) =>
      arr.map((item, n) => (n === idx ? { ...item, [field]: e.target.value } : item)),
    )

  const autoTotal = () => {
    const sum = items.reduce((s, i) => s + (parseFloat(i.price) || 0), 0)
    setForm((f) => ({ ...f, total: sum.toFixed(2) }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    if (!form.store.trim()) { setError('Store name is required.'); return }
    const payload = {
      date: form.date,
      store: form.store.trim(),
      total: parseFloat(form.total) || 0,
      notes: form.notes.trim() || null,
      items: items
        .filter((i) => i.name.trim())
        .map((i) => ({ name: i.name.trim(), price: parseFloat(i.price) || 0 })),
    }
    setSaving(true)
    try {
      await createExpense(payload)
      setSaved(true)
      setTimeout(() => navigate('/dashboard'), 1500)
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
    } finally {
      setSaving(false)
    }
  }

  if (saved) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <CheckCircle2 size={48} className="text-green-400" />
        <p className="text-white font-semibold text-lg">Expense saved!</p>
        <p className="text-slate-400 text-sm">Redirecting to dashboard…</p>
      </div>
    )
  }

  return (
    <div className="max-w-2xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">Add Expense</h1>
        <p className="text-slate-400 text-sm mt-0.5">Record a new purchase or payment</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* ── Basic info ─────────────────────────────────────────────────── */}
        <div className="card p-5 space-y-4">
          <h2 className="font-semibold text-white text-sm uppercase tracking-wider text-slate-400">
            Details
          </h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Date</label>
              <input type="date" className="input" value={form.date} onChange={set('date')} required />
            </div>
            <div>
              <label className="label">Store / Merchant</label>
              <input
                type="text"
                className="input"
                placeholder="e.g. Whole Foods"
                value={form.store}
                onChange={set('store')}
                required
              />
            </div>
          </div>
          <div>
            <label className="label">Notes (optional)</label>
            <textarea
              className="input resize-none h-20"
              placeholder="Any additional notes…"
              value={form.notes}
              onChange={set('notes')}
            />
          </div>
        </div>

        {/* ── Items ──────────────────────────────────────────────────────── */}
        <div className="card p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-white text-sm uppercase tracking-wider text-slate-400">
              Items
            </h2>
            <button type="button" onClick={addItem} className="btn-secondary text-xs py-1">
              <Plus size={13} /> Add Item
            </button>
          </div>

          <div className="space-y-2">
            {items.map((item, idx) => (
              <div key={idx} className="flex gap-2 items-center">
                <input
                  type="text"
                  className="input flex-1"
                  placeholder={`Item ${idx + 1} name`}
                  value={item.name}
                  onChange={setItem(idx, 'name')}
                />
                <input
                  type="number"
                  className="input w-28"
                  placeholder="Price"
                  min="0"
                  step="0.01"
                  value={item.price}
                  onChange={setItem(idx, 'price')}
                />
                <button
                  type="button"
                  onClick={() => removeItem(idx)}
                  className="btn-danger p-2 shrink-0"
                  disabled={items.length === 1}
                >
                  <Minus size={14} />
                </button>
              </div>
            ))}
          </div>

          <button
            type="button"
            onClick={autoTotal}
            className="btn-secondary text-xs py-1"
          >
            Auto-calculate Total
          </button>
        </div>

        {/* ── Total & submit ─────────────────────────────────────────────── */}
        <div className="card p-5 space-y-4">
          <div>
            <label className="label">Total ($)</label>
            <input
              type="number"
              className="input text-xl font-bold"
              placeholder="0.00"
              min="0"
              step="0.01"
              value={form.total}
              onChange={set('total')}
              required
            />
          </div>

          {error && (
            <p className="text-red-400 text-sm bg-red-900/20 border border-red-800/30 rounded-xl px-4 py-2">
              {error}
            </p>
          )}

          <button type="submit" disabled={saving} className="btn-primary w-full justify-center py-3">
            {saving ? (
              <>
                <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Saving…
              </>
            ) : (
              <>
                <Save size={16} />
                Save Expense
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  )
}
