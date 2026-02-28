import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  CalendarDays,
  PlusCircle,
  Camera,
  TrendingUp,
} from 'lucide-react'

const links = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/monthly', icon: CalendarDays, label: 'Monthly' },
  { to: '/add', icon: PlusCircle, label: 'Add Expense' },
  { to: '/upload', icon: Camera, label: 'Upload Receipt' },
]

export default function Sidebar() {
  return (
    <aside className="w-60 shrink-0 bg-slate-900 border-r border-slate-800 flex flex-col">
      {/* Logo */}
      <div className="flex items-center gap-3 px-5 py-6 border-b border-slate-800">
        <span className="text-2xl">💰</span>
        <div>
          <p className="text-white font-semibold text-sm leading-tight">My Finance</p>
          <p className="text-slate-500 text-xs">Expense Tracker</p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 p-3 space-y-1">
        {links.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) => isActive ? 'nav-item-active' : 'nav-item'}
          >
            <Icon size={18} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-slate-800">
        <div className="flex items-center gap-2 text-slate-500 text-xs">
          <TrendingUp size={14} />
          <span>Track every dollar</span>
        </div>
      </div>
    </aside>
  )
}
