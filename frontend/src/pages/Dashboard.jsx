import { useEffect, useState } from 'react'
import { format } from 'date-fns'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from 'recharts'
import {
  DollarSign, ShoppingCart, TrendingUp, Calendar,
  ArrowUpRight, ArrowDownRight,
} from 'lucide-react'
import { getExpenses, getMonthlySummary } from '../api'

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

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
            {p.name}: <span className="font-bold">${Number(p.value).toFixed(2)}</span>
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
  const [error, setError] = useState(null)

  useEffect(() => {
    setLoading(true)
    Promise.all([getExpenses(), getMonthlySummary()])
      .then(([exp, monthly]) => {
        setExpenses(exp)
        setMonthlySummary(monthly)
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <LoadingState />
  if (error) return <ErrorState message={error} />

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
    Total: +m.total.toFixed(2),
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
          label="This Month"
          value={`$${thisMonthTotal.toFixed(2)}`}
          sub={
            lastMonthTotal ? (
              <span className={monthChange >= 0 ? 'text-red-400 flex items-center gap-0.5' : 'text-green-400 flex items-center gap-0.5'}>
                {monthChange >= 0 ? <ArrowUpRight size={13} /> : <ArrowDownRight size={13} />}
                {Math.abs(monthChange).toFixed(1)}% vs last month
              </span>
            ) : null
          }
          accent="from-brand-600/20 to-brand-900/10"
          iconBg="bg-brand-500/20 text-brand-400"
        />
        <StatCard
          icon={<ShoppingCart size={18} />}
          label="Total Expenses"
          value={expenses.length}
          sub={`${thisMonthData?.count ?? 0} this month`}
          accent="from-violet-600/20 to-violet-900/10"
          iconBg="bg-violet-500/20 text-violet-400"
        />
        <StatCard
          icon={<TrendingUp size={18} />}
          label="All-Time Spent"
          value={`$${totalAllTime.toFixed(2)}`}
          sub={`across ${monthlySummary.length} months`}
          accent="from-pink-600/20 to-pink-900/10"
          iconBg="bg-pink-500/20 text-pink-400"
        />
        <StatCard
          icon={<Calendar size={18} />}
          label="Avg per Expense"
          value={`$${avgExpense.toFixed(2)}`}
          sub="across all time"
          accent="from-amber-600/20 to-amber-900/10"
          iconBg="bg-amber-500/20 text-amber-400"
        />
      </div>

      {/* ── Charts row ───────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 xl:grid-cols-5 gap-4">
        {/* Monthly bar chart */}
        <div className="card p-5 xl:col-span-3">
          <h2 className="font-semibold text-white mb-4">Monthly Spending</h2>
          {barData.length > 0 ? (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={barData} barCategoryGap="30%">
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                <XAxis dataKey="name" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tickFormatter={(v) => `$${v}`} tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="Total" fill="#6366f1" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyChart />
          )}
        </div>

        {/* Spending by store pie */}
        <div className="card p-5 xl:col-span-2">
          <h2 className="font-semibold text-white mb-4">Spending by Store</h2>
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
          <h2 className="font-semibold text-white">Recent Expenses</h2>
          <span className="text-xs text-slate-500">{expenses.length} total</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-800">
                <Th>Date</Th>
                <Th>Store</Th>
                <Th>Items</Th>
                <Th align="right">Total</Th>
              </tr>
            </thead>
            <tbody>
              {recent.length === 0 ? (
                <tr>
                  <td colSpan={4} className="text-center py-10 text-slate-500">
                    No expenses yet
                  </td>
                </tr>
              ) : (
                recent.map((e) => (
                  <tr key={e.id} className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors">
                    <Td>{format(new Date(e.date), 'MMM d, yyyy')}</Td>
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
                      <span className="font-semibold text-brand-400">${e.total.toFixed(2)}</span>
                    </Td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

/* ── Small sub-components ───────────────────────────────────────────────── */

function Header() {
  const now = new Date()
  return (
    <div className="flex items-center justify-between">
      <div>
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <p className="text-slate-400 text-sm mt-0.5">
          {format(now, 'EEEE, MMMM d yyyy')}
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
    <th className={`px-5 py-3 text-xs font-medium text-slate-400 uppercase tracking-wider ${align === 'right' ? 'text-right' : 'text-left'}`}>
      {children}
    </th>
  )
}

function Td({ children, align = 'left' }) {
  return <td className={`px-5 py-3.5 text-slate-300 ${align === 'right' ? 'text-right' : 'text-left'}`}>{children}</td>
}

function LoadingState() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="flex flex-col items-center gap-3">
        <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
        <p className="text-slate-400 text-sm">Loading dashboard…</p>
      </div>
    </div>
  )
}

function ErrorState({ message }) {
  return (
    <div className="card p-8 text-center">
      <p className="text-red-400 font-medium">Failed to load data</p>
      <p className="text-slate-500 text-sm mt-1">{message}</p>
    </div>
  )
}

function EmptyChart() {
  return (
    <div className="h-60 flex items-center justify-center text-slate-500 text-sm">
      No data to display
    </div>
  )
}
