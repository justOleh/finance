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

// --- Async receipt pipeline (ADR-010) ---------------------------------------
// 1. ask the backend for a presigned POST, 2. send the image straight to S3,
// 3. poll the receipt until the worker has parsed it.
export const requestReceiptUpload = (contentType) =>
  api.post('/receipts/upload-url', { content_type: contentType }).then((r) => r.data)

// Plain axios on purpose: this goes to S3, so it must NOT carry the app's Authorization header
// (the presigned fields are the credentials). S3 requires the file to be the last form field.
export const uploadToS3 = ({ upload_url, fields }, file) => {
  const fd = new FormData()
  Object.entries(fields).forEach(([k, v]) => fd.append(k, v))
  fd.append('file', file)
  return axios.post(upload_url, fd, { timeout: UPLOAD_TIMEOUT_MS })
}

export const getReceipt = (id) =>
  api.get(`/receipts/${id}`).then((r) => r.data)
