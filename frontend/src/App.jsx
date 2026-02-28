import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import MonthlyView from './pages/MonthlyView'
import AddExpense from './pages/AddExpense'
import UploadReceipt from './pages/UploadReceipt'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="monthly" element={<MonthlyView />} />
          <Route path="add" element={<AddExpense />} />
          <Route path="upload" element={<UploadReceipt />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
