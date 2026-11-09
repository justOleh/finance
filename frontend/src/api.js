import axios from 'axios'
import { authEnabled, getAccessToken, signOut } from './auth'

const BASE = import.meta.env.VITE_BACKEND_URL || ''
const UPLOAD_TIMEOUT_MS = 120000

const api = axios.create({
  baseURL: BASE,
  timeout: 15000,
})

// Attach the Cognito access token (getAccessToken refreshes it when it has expired).
// Only for calls to our backend: never send it to S3 presigned URLs.
api.interceptors.request.use(async (config) => {
  if (authEnabled) {
    const token = await getAccessToken()
    if (token) config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// A 401 means the session is no longer valid (refresh token expired or revoked):
// sign out, and ProtectedRoute sends the user to /login.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (authEnabled && error.response?.status === 401) signOut()
    return Promise.reject(error)
  },
)

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
