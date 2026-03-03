import axios from 'axios'

const BASE = import.meta.env.VITE_BACKEND_URL || ''
const UPLOAD_TIMEOUT_MS = 120000

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
    timeout: UPLOAD_TIMEOUT_MS,
  }).then((r) => r.data)

export const parseReceipt = (formData) =>
  api.post('/receipts/parse', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: UPLOAD_TIMEOUT_MS,
  }).then((r) => r.data)
