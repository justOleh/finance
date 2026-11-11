import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, ProtectedRoute } from './AuthContext'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Login from './pages/Login'
import MonthlyView from './pages/MonthlyView'
import AddExpense from './pages/AddExpense'
import UploadReceipt from './pages/UploadReceipt'
import Chat from './pages/Chat'

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<Layout />}>
              <Route index element={<Navigate to="/dashboard" replace />} />
              <Route path="dashboard" element={<Dashboard />} />
              <Route path="monthly" element={<MonthlyView />} />
              <Route path="add" element={<AddExpense />} />
              <Route path="upload" element={<UploadReceipt />} />
              <Route path="chat" element={<Chat />} />
            </Route>
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
