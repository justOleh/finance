import { useEffect, useState } from 'react'
import { format } from 'date-fns'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { ChevronLeft, ChevronRight, Trash2 } from 'lucide-react'
import { getExpenses, deleteExpense } from '../api'

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
]

export default function MonthlyView() {
  const now = new Date()
  const [year, setYear] = useState(now.getFullYear())
  const [month, setMonth] = useState(now.getMonth() + 1)
  const [expenses, setExpenses] = useState([])
  const [loading, setLoading] = useState(false)
  const [deletingId, setDeletingId] = useState(null)

  const fetchData = () => {
    setLoading(true)
    const startDate = `${year}-${String(month).padStart(2, '0')}-01`
    const lastDay = new Date(year, month, 0).getDate()
    const endDate = `${year}-${String(month).padStart(2, '0')}-${lastDay}`
    getExpenses({ start_date: startDate, end_date: endDate })
      .then(setExpenses)
      .catch(console.error)
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchData() }, [year, month]) // eslint-disable-line

  const prevMonth = () => {
    if (month === 1) { setYear(y => y - 1); setMonth(12) }
    else setMonth(m => m - 1)
  }
  const nextMonth = () => {
    if (month === 12) { setYear(y => y + 1); setMonth(1) }
    else setMonth(m => m + 1)
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this expense?')) return
    setDeletingId(id)
    await deleteExpense(id).catch(console.error)
    setDeletingId(null)
    fetchData()
  }

  // ── Derived stats ────────────────────────────────────────────────────────
  const total = expenses.reduce((s, e) => s + e.total, 0)
  const avg = expenses.length ? total / expenses.length : 0

  // Daily spending for area chart
  const dailyMap = expenses.reduce((acc, e) => {
    const d = e.date
    acc[d] = (acc[d] ?? 0) + e.total
    return acc
  }, {})
  const dailyData = Object.entries(dailyMap)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, amount]) => ({
      date: format(new Date(date), 'MMM d'),
      amount: +amount.toFixed(2),
    }))

  // Top stores
  const byStore = expenses.reduce((acc, e) => {
    acc[e.store] = (acc[e.store] ?? 0) + e.total
    return acc
  }, {})
  const topStores = Object.entries(byStore)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
  const maxStoreTotal = topStores[0]?.[1] ?? 1

  return (
    <div className="space-y-6">
      {/* Header with month navigation */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Monthly View</h1>
          <p className="text-slate-400 text-sm mt-0.5">
            Detailed breakdown by month
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={prevMonth} className="btn-secondary p-2">
            <ChevronLeft size={16} />
          </button>
          <span className="px-4 py-2 card text-white font-semibold text-sm min-w-[140px] text-center">
            {MONTH_NAMES[month - 1]} {year}
          </span>
          <button onClick={nextMonth} className="btn-secondary p-2">
            <ChevronRight size={16} />
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-16">
          <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : (
        <>
          {/* ── Stat cards ─────────────────────────────────────────────── */}
          <div className="grid grid-cols-3 gap-4">
            <div className="stat-card">
              <span className="stat-label">Total Spent</span>
              <span className="stat-value text-brand-400">${total.toFixed(2)}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Transactions</span>
              <span className="stat-value">{expenses.length}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Avg per Transaction</span>
              <span className="stat-value">${avg.toFixed(2)}</span>
            </div>
          </div>

          {/* ── Charts row ──────────────────────────────────────────────── */}
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
            {/* Daily spending area chart */}
            <div className="card p-5 xl:col-span-2">
              <h2 className="font-semibold text-white mb-4">Daily Spending</h2>
              {dailyData.length > 0 ? (
                <ResponsiveContainer width="100%" height={200}>
                  <AreaChart data={dailyData}>
                    <defs>
                      <linearGradient id="colorAmt" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                    <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
                    <YAxis tickFormatter={(v) => `$${v}`} tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
                    <Tooltip
                      contentStyle={{ background: '#0f172a', border: '1px solid #1e293b', borderRadius: 12 }}
                      labelStyle={{ color: '#f1f5f9' }}
                      itemStyle={{ color: '#818cf8' }}
                    />
                    <Area
                      type="monotone"
                      dataKey="amount"
                      stroke="#6366f1"
                      strokeWidth={2}
                      fill="url(#colorAmt)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-48 flex items-center justify-center text-slate-500 text-sm">
                  No expenses this month
                </div>
              )}
            </div>

            {/* Top stores */}
            <div className="card p-5">
              <h2 className="font-semibold text-white mb-4">Top Stores</h2>
              {topStores.length > 0 ? (
                <div className="space-y-3">
                  {topStores.map(([store, amount]) => (
                    <div key={store}>
                      <div className="flex justify-between text-sm mb-1">
                        <span className="text-slate-300 truncate max-w-[120px]">{store}</span>
                        <span className="text-brand-400 font-medium">${amount.toFixed(2)}</span>
                      </div>
                      <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-brand-500 rounded-full transition-all"
                          style={{ width: `${(amount / maxStoreTotal) * 100}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-slate-500 text-sm">No data</p>
              )}
            </div>
          </div>

          {/* ── Expense list ─────────────────────────────────────────────── */}
          <div className="card overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-800">
              <h2 className="font-semibold text-white">
                All Expenses – {MONTH_NAMES[month - 1]} {year}
              </h2>
            </div>
            {expenses.length === 0 ? (
              <div className="py-16 text-center text-slate-500">
                No expenses recorded for this month
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-800">
                      <Th>Date</Th>
                      <Th>Store</Th>
                      <Th>Items</Th>
                      <Th>Notes</Th>
                      <Th align="right">Total</Th>
                      <Th align="center">Actions</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {expenses.map((e) => (
                      <tr
                        key={e.id}
                        className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors"
                      >
                        <Td>{format(new Date(e.date), 'MMM d')}</Td>
                        <Td>
                          <span className="font-medium text-white">{e.store}</span>
                        </Td>
                        <Td>
                          <span className="text-slate-400 text-xs">
                            {e.items?.length
                              ? e.items.map((i) => i.name).join(', ')
                              : '—'}
                          </span>
                        </Td>
                        <Td>
                          <span className="text-slate-500 text-xs">{e.notes || '—'}</span>
                        </Td>
                        <Td align="right">
                          <span className="font-semibold text-brand-400">${e.total.toFixed(2)}</span>
                        </Td>
                        <Td align="center">
                          <button
                            onClick={() => handleDelete(e.id)}
                            disabled={deletingId === e.id}
                            className="btn-danger px-2 py-1 text-xs"
                          >
                            <Trash2 size={12} />
                          </button>
                        </Td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}

function Th({ children, align = 'left' }) {
  return (
    <th className={`px-5 py-3 text-xs font-medium text-slate-400 uppercase tracking-wider ${align === 'right' ? 'text-right' : align === 'center' ? 'text-center' : 'text-left'}`}>
      {children}
    </th>
  )
}

function Td({ children, align = 'left' }) {
  return <td className={`px-5 py-3 text-slate-300 ${align === 'right' ? 'text-right' : align === 'center' ? 'text-center' : 'text-left'}`}>{children}</td>
}
