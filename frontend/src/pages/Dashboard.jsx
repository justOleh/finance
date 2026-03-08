import { useEffect, useState } from 'react'
import { format } from 'date-fns'
import { uk } from 'date-fns/locale'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from 'recharts'
import {
  DollarSign, ShoppingCart, TrendingUp, Calendar,
  ArrowUpRight, ArrowDownRight, Pencil, Trash2, Plus,
} from 'lucide-react'
import { getExpenses, getMonthlySummary, updateExpense, deleteExpense } from '../api'

const MONTH_NAMES = ['січ', 'лют', 'бер', 'кві', 'тра', 'чер',
  'лип', 'сер', 'вер', 'жов', 'лис', 'гру']

const formatCurrencyUAH = (value) => new Intl.NumberFormat('uk-UA', {
  style: 'currency',
  currency: 'UAH',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
}).format(Number(value) || 0)

const STORE_COLORS = [
  '#6366f1', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981',
  '#3b82f6', '#ef4444', '#14b8a6', '#f97316', '#84cc16',
]

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload?.length) {
    return (
      <div className="card p-3 text-sm shadow-2xl">
        <p className="font-semibold text-white mb-1">{label}</p>
        {payload.map((p) => (
          <p key={p.name} style={{ color: p.color }}>
            {p.name}: <span className="font-bold">{formatCurrencyUAH(p.value)}</span>
          </p>
        ))}
      </div>
    )
  }
  return null
}

export default function Dashboard() {
  const [expenses, setExpenses] = useState([])
  const [monthlySummary, setMonthlySummary] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [actionError, setActionError] = useState(null)
  const [editing, setEditing] = useState(null)
  const [savingEdit, setSavingEdit] = useState(false)
  const [deletingId, setDeletingId] = useState(null)

  const fetchData = () => {
    setLoading(true)
    Promise.all([getExpenses(), getMonthlySummary()])
      .then(([exp, monthly]) => {
        setExpenses(exp)
        setMonthlySummary(monthly)
      })
      .catch((e) => setLoadError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchData()
  }, [])

  const startEdit = (expense) => {
    setEditing({
      id: expense.id,
      date: String(expense.date || '').slice(0, 10),
      store: expense.store || '',
      total: Number(expense.total || 0).toFixed(2),
      notes: expense.notes || '',
      items: (expense.items || []).map((item) => ({
        name: item?.name || '',
        price: Number(item?.price ?? item?.item_price ?? 0).toFixed(2),
      })),
    })
  }

  const setEditingField = (field) => (e) => {
    const value = e.target.value
    setEditing((prev) => ({ ...prev, [field]: value }))
  }

  const setEditingItem = (idx, field) => (e) => {
    const value = e.target.value
    setEditing((prev) => ({
      ...prev,
      items: prev.items.map((item, i) => (i === idx ? { ...item, [field]: value } : item)),
    }))
  }

  const addEditingItem = () => {
    setEditing((prev) => ({
      ...prev,
      items: [...(prev.items || []), { name: '', price: '0.00' }],
    }))
  }

  const deleteEditingItem = (idx) => {
    setEditing((prev) => ({
      ...prev,
      items: prev.items.filter((_, i) => i !== idx),
    }))
  }

  const recalcEditingTotal = () => {
    setEditing((prev) => {
      const sum = (prev.items || []).reduce((s, item) => s + (Number(item.price) || 0), 0)
      return { ...prev, total: sum.toFixed(2) }
    })
  }

  const saveEdit = async () => {
    if (!editing) return
    if (!editing.store?.trim()) {
      setActionError('Вкажіть назву магазину')
      return
    }

    setSavingEdit(true)
    setActionError(null)
    try {
      await updateExpense(editing.id, {
        date: editing.date,
        store: editing.store.trim(),
        total: Number(editing.total) || 0,
        notes: editing.notes?.trim() || null,
        items: (editing.items || [])
          .filter((item) => item.name?.trim())
          .map((item) => ({ name: item.name.trim(), price: Number(item.price) || 0 })),
      })
      setEditing(null)
      fetchData()
    } catch (e) {
      setActionError(e.response?.data?.detail || e.message)
    } finally {
      setSavingEdit(false)
    }
  }

  const handleDelete = async (expenseId) => {
    if (!confirm('Видалити цю витрату?')) return
    setDeletingId(expenseId)
    try {
      await deleteExpense(expenseId)
      if (editing?.id === expenseId) setEditing(null)
      fetchData()
    } catch (e) {
      setActionError(e.response?.data?.detail || e.message)
    } finally {
      setDeletingId(null)
    }
  }

  if (loading) return <LoadingState />
  if (loadError) return <ErrorState message={loadError} />

  // ── Derived stats ────────────────────────────────────────────────────────
  const currentMonth = new Date().getMonth() + 1
  const currentYear = new Date().getFullYear()
  const thisMonthData = monthlySummary.find(
    (m) => m.year === currentYear && m.month === currentMonth,
  )
  const lastMonthData = (() => {
    const lm = currentMonth === 1 ? 12 : currentMonth - 1
    const ly = currentMonth === 1 ? currentYear - 1 : currentYear
    return monthlySummary.find((m) => m.year === ly && m.month === lm)
  })()

  const totalAllTime = expenses.reduce((s, e) => s + e.total, 0)
  const avgExpense = expenses.length ? totalAllTime / expenses.length : 0
  const thisMonthTotal = thisMonthData?.total ?? 0
  const lastMonthTotal = lastMonthData?.total ?? 0
  const monthChange = lastMonthTotal
    ? ((thisMonthTotal - lastMonthTotal) / lastMonthTotal) * 100
    : 0

  // ── Chart data ────────────────────────────────────────────────────────────
  const barData = monthlySummary.slice(-8).map((m) => ({
    name: `${MONTH_NAMES[m.month - 1]} ${m.year}`,
    Сума: +m.total.toFixed(2),
  }))

  const byStore = expenses.reduce((acc, e) => {
    acc[e.store] = (acc[e.store] ?? 0) + e.total
    return acc
  }, {})
  const pieData = Object.entries(byStore)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([name, value]) => ({ name, value: +value.toFixed(2) }))

  const recent = [...expenses].slice(0, 8)

  return (
    <div className="space-y-6">
      <Header />

      {/* ── Stat cards ───────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={<DollarSign size={18} />}
          label="Цього місяця"
          value={formatCurrencyUAH(thisMonthTotal)}
          sub={
            lastMonthTotal ? (
              <span className={monthChange >= 0 ? 'text-red-400 flex items-center gap-0.5' : 'text-green-400 flex items-center gap-0.5'}>
                {monthChange >= 0 ? <ArrowUpRight size={13} /> : <ArrowDownRight size={13} />}
                {Math.abs(monthChange).toFixed(1)}% проти минулого місяця
              </span>
            ) : null
          }
          accent="from-brand-600/20 to-brand-900/10"
          iconBg="bg-brand-500/20 text-brand-400"
        />
        <StatCard
          icon={<ShoppingCart size={18} />}
          label="Усього витрат"
          value={expenses.length}
          sub={`${thisMonthData?.count ?? 0} цього місяця`}
          accent="from-violet-600/20 to-violet-900/10"
          iconBg="bg-violet-500/20 text-violet-400"
        />
        <StatCard
          icon={<TrendingUp size={18} />}
          label="Витрачено за весь час"
          value={formatCurrencyUAH(totalAllTime)}
          sub={`за ${monthlySummary.length} міс.`}
          accent="from-pink-600/20 to-pink-900/10"
          iconBg="bg-pink-500/20 text-pink-400"
        />
        <StatCard
          icon={<Calendar size={18} />}
          label="Середня витрата"
          value={formatCurrencyUAH(avgExpense)}
          sub="за весь час"
          accent="from-amber-600/20 to-amber-900/10"
          iconBg="bg-amber-500/20 text-amber-400"
        />
      </div>

      {/* ── Charts row ───────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 xl:grid-cols-5 gap-4">
        {/* Monthly bar chart */}
        <div className="card p-5 xl:col-span-3">
          <h2 className="font-semibold text-white mb-4">Витрати по місяцях</h2>
          {barData.length > 0 ? (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={barData} barCategoryGap="30%">
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                <XAxis dataKey="name" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tickFormatter={(v) => formatCurrencyUAH(v)} tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="Сума" fill="#6366f1" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyChart />
          )}
        </div>

        {/* Spending by store pie */}
        <div className="card p-5 xl:col-span-2">
          <h2 className="font-semibold text-white mb-4">Витрати по магазинах</h2>
          {pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="45%"
                  innerRadius={55}
                  outerRadius={85}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {pieData.map((_, i) => (
                    <Cell key={i} fill={STORE_COLORS[i % STORE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip content={<CustomTooltip />} />
                <Legend
                  formatter={(v) => <span style={{ color: '#94a3b8', fontSize: 11 }}>{v}</span>}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <EmptyChart />
          )}
        </div>
      </div>

      {/* ── Recent expenses table ─────────────────────────────────────────── */}
      <div className="card overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-800 flex items-center justify-between">
          <h2 className="font-semibold text-white">Останні витрати</h2>
          <span className="text-xs text-slate-500">{expenses.length} всього</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-800">
                <Th>Дата</Th>
                <Th>Магазин</Th>
                <Th>Позиції</Th>
                <Th align="right">Сума</Th>
                <Th align="center">Дії</Th>
              </tr>
            </thead>
            <tbody>
              {recent.length === 0 ? (
                <tr>
                  <td colSpan={5} className="text-center py-10 text-slate-500">
                    Поки немає витрат
                  </td>
                </tr>
              ) : (
                recent.map((e) => (
                  <tr key={e.id} className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors">
                    <Td>{format(new Date(e.date), 'd MMM yyyy', { locale: uk })}</Td>
                    <Td>
                      <span className="font-medium text-white">{e.store}</span>
                    </Td>
                    <Td>
                      <span className="text-slate-400">
                        {e.items?.length
                          ? e.items.slice(0, 2).map((i) => i.name).join(', ') +
                            (e.items.length > 2 ? ` +${e.items.length - 2}` : '')
                          : '—'}
                      </span>
                    </Td>
                    <Td align="right">
                      <span className="font-semibold text-brand-400">{formatCurrencyUAH(e.total)}</span>
                    </Td>
                    <Td align="center">
                      <div className="flex items-center justify-center gap-2">
                        <button
                          onClick={() => startEdit(e)}
                          className="btn-secondary px-2 py-1 text-xs"
                        >
                          <Pencil size={12} />
                        </button>
                        <button
                          onClick={() => handleDelete(e.id)}
                          disabled={deletingId === e.id}
                          className="btn-danger px-2 py-1 text-xs"
                        >
                          <Trash2 size={12} />
                        </button>
                      </div>
                    </Td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {editing && (
        <div className="card p-5 space-y-4">
          <h2 className="font-semibold text-white">Редагувати витрату</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="label">Дата</label>
              <input type="date" className="input" value={editing.date} onChange={setEditingField('date')} />
            </div>
            <div>
              <label className="label">Магазин</label>
              <input className="input" value={editing.store} onChange={setEditingField('store')} />
            </div>
            <div>
              <label className="label">Сума (грн)</label>
              <input type="number" min="0" step="0.01" className="input" value={editing.total} onChange={setEditingField('total')} />
            </div>
            <div>
              <label className="label">Нотатки</label>
              <input className="input" value={editing.notes} onChange={setEditingField('notes')} />
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <p className="label">Позиції</p>
              <div className="flex gap-2">
                <button type="button" onClick={recalcEditingTotal} className="btn-secondary text-xs py-1 px-2">
                  Перерахувати суму
                </button>
                <button type="button" onClick={addEditingItem} className="btn-secondary text-xs py-1 px-2">
                  <Plus size={12} /> Додати
                </button>
              </div>
            </div>
            <div className="space-y-2">
              {(editing.items || []).length === 0 ? (
                <p className="text-slate-500 text-sm">Позицій немає</p>
              ) : (
                editing.items.map((item, idx) => (
                  <div key={idx} className="flex gap-2 items-center">
                    <input
                      className="input flex-1"
                      placeholder="Назва"
                      value={item.name}
                      onChange={setEditingItem(idx, 'name')}
                    />
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      className="input w-24 sm:w-32"
                      placeholder="Ціна"
                      value={item.price}
                      onChange={setEditingItem(idx, 'price')}
                    />
                    <button
                      type="button"
                      className="btn-danger px-2 py-2"
                      onClick={() => deleteEditingItem(idx)}
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>

          {actionError && (
            <div className="flex items-center gap-2 text-red-400 text-sm bg-red-900/20 border border-red-800/30 rounded-xl px-4 py-3">
              {actionError}
            </div>
          )}

          <div className="flex gap-3">
            <button onClick={saveEdit} disabled={savingEdit} className="btn-primary px-4 py-2">
              {savingEdit ? 'Збереження…' : 'Зберегти зміни'}
            </button>
            <button onClick={() => setEditing(null)} className="btn-secondary px-4 py-2">
              Скасувати
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

/* ── Small sub-components ───────────────────────────────────────────────── */

function Header() {
  const now = new Date()
  return (
    <div className="flex items-center justify-between">
      <div>
        <h1 className="text-xl sm:text-2xl font-bold text-white">Панель</h1>
        <p className="text-slate-400 text-sm mt-0.5">
          {format(now, 'EEEE, d MMMM yyyy', { locale: uk })}
        </p>
      </div>
    </div>
  )
}

function StatCard({ icon, label, value, sub, accent, iconBg }) {
  return (
    <div className={`stat-card bg-gradient-to-br ${accent}`}>
      <div className="flex items-center justify-between">
        <span className="stat-label">{label}</span>
        <span className={`p-1.5 rounded-lg ${iconBg}`}>{icon}</span>
      </div>
      <span className="stat-value">{value}</span>
      {sub && <div className="text-xs text-slate-400">{sub}</div>}
    </div>
  )
}

function Th({ children, align = 'left' }) {
  return (
    <th className={`px-3 sm:px-5 py-3 text-xs font-medium text-slate-400 uppercase tracking-wider whitespace-nowrap ${align === 'right' ? 'text-right' : 'text-left'}`}>
      {children}
    </th>
  )
}

function Td({ children, align = 'left' }) {
  return <td className={`px-3 sm:px-5 py-3 text-slate-300 ${align === 'right' ? 'text-right' : 'text-left'}`}>{children}</td>
}

function LoadingState() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="flex flex-col items-center gap-3">
        <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
        <p className="text-slate-400 text-sm">Завантаження панелі…</p>
      </div>
    </div>
  )
}

function ErrorState({ message }) {
  return (
    <div className="card p-8 text-center">
      <p className="text-red-400 font-medium">Не вдалося завантажити дані</p>
      <p className="text-slate-500 text-sm mt-1">{message}</p>
    </div>
  )
}

function EmptyChart() {
  return (
    <div className="h-60 flex items-center justify-center text-slate-500 text-sm">
      Немає даних для відображення
    </div>
  )
}
