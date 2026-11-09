import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { authEnabled, getSession, sessionEmail, signIn, signOut, SIGNED_OUT_EVENT } from './auth'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  // `loading` is true until the stored session (if any) has been checked.
  const [state, setState] = useState({ loading: authEnabled, email: authEnabled ? null : 'local' })

  const refresh = useCallback(async () => {
    const session = await getSession()
    setState({ loading: false, email: sessionEmail(session) })
  }, [])

  useEffect(() => {
    if (!authEnabled) return undefined
    refresh()
    // Fired by signOut() and by the API client when the backend answers 401.
    const onSignedOut = () => setState({ loading: false, email: null })
    window.addEventListener(SIGNED_OUT_EVENT, onSignedOut)
    return () => window.removeEventListener(SIGNED_OUT_EVENT, onSignedOut)
  }, [refresh])

  const value = useMemo(
    () => ({
      ...state,
      authEnabled,
      login: async (email, password) => {
        await signIn(email, password)
        await refresh()
      },
      logout: signOut,
    }),
    [state, refresh],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)

// Wrap routes that need a signed-in user; everyone else is sent to /login.
export function ProtectedRoute() {
  const { loading, email } = useAuth()
  const location = useLocation()

  if (loading) return <div className="min-h-screen flex items-center justify-center text-slate-500">…</div>
  if (!email) return <Navigate to="/login" replace state={{ from: location }} />
  return <Outlet />
}
