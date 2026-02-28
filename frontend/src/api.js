import axios from 'axios'

const BASE = import.meta.env.VITE_BACKEND_URL || ''

const api = axios.create({
  baseURL: BASE,
  timeout: 15000,
})

export const getExpenses = (params = {}) =>
  api.get('/expenses/', { params }).then((r) => r.data)

export const getMonthlySummary = () =>
  api.get('/expenses/monthly-summary').then((r) => r.data)

export const createExpense = (payload) =>
  api.post('/expenses/', payload).then((r) => r.data)

export const updateExpense = (id, payload) =>
  api.put(`/expenses/${id}`, payload).then((r) => r.data)

export const deleteExpense = (id) =>
  api.delete(`/expenses/${id}`)

export const uploadReceipt = (formData) =>
  api.post('/receipts/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 30000,
  }).then((r) => r.data)
