import { useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { LogIn } from 'lucide-react'
import { useAuth } from '../AuthContext'
import { NEW_PASSWORD_REQUIRED } from '../auth'

function errorMessage(err) {
  switch (err?.code) {
    case 'NotAuthorizedException':
    case 'UserNotFoundException':
      return 'Невірний email або пароль'
    case NEW_PASSWORD_REQUIRED:
      return 'Потрібно встановити постійний пароль (admin-set-user-password --permanent)'
    case 'TooManyRequestsException':
    case 'LimitExceededException':
      return 'Забагато спроб. Спробуйте пізніше'
    default:
      return 'Не вдалося увійти. Спробуйте ще раз'
  }
}

export default function Login() {
  const { email: signedInAs, login } = useAuth()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  if (signedInAs) return <Navigate to={location.state?.from?.pathname || '/dashboard'} replace />

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      await login(email.trim(), password)
    } catch (err) {
      setError(errorMessage(err))
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <form onSubmit={handleSubmit} className="card p-6 w-full max-w-sm space-y-4">
        <div className="flex items-center gap-3 mb-2">
          <span className="text-2xl">💰</span>
          <div>
            <h1 className="text-white font-semibold leading-tight">My Finance</h1>
            <p className="text-slate-500 text-xs">Увійдіть, щоб продовжити</p>
          </div>
        </div>

        <div>
          <label className="label" htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            autoComplete="username"
            className="input"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoFocus
          />
        </div>

        <div>
          <label className="label" htmlFor="password">Пароль</label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            className="input"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>

        {error && <p role="alert" className="text-sm text-red-400">{error}</p>}

        <button type="submit" className="btn-primary w-full justify-center" disabled={busy}>
          <LogIn size={16} />
          {busy ? 'Входимо…' : 'Увійти'}
        </button>
      </form>
    </div>
  )
}
