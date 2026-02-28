import { useState, useRef } from 'react'
import { Upload, ImageIcon, CheckCircle2, XCircle } from 'lucide-react'
import { uploadReceipt } from '../api'
import { format } from 'date-fns'

export default function UploadReceipt() {
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef(null)

  const handleFile = (f) => {
    if (!f) return
    if (!['image/jpeg', 'image/png', 'image/jpg'].includes(f.type)) {
      setError('Only JPEG and PNG files are supported.')
      return
    }
    setFile(f)
    setError(null)
    setResult(null)
    const reader = new FileReader()
    reader.onload = (e) => setPreview(e.target.result)
    reader.readAsDataURL(f)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    handleFile(e.dataTransfer.files[0])
  }

  const handleUpload = async () => {
    if (!file) return
    setUploading(true)
    setError(null)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const data = await uploadReceipt(fd)
      setResult(data)
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
    } finally {
      setUploading(false)
    }
  }

  const reset = () => {
    setFile(null)
    setPreview(null)
    setResult(null)
    setError(null)
  }

  return (
    <div className="max-w-2xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">Upload Receipt</h1>
        <p className="text-slate-400 text-sm mt-0.5">
          Upload a photo and we'll extract the data automatically
        </p>
      </div>

      {!result ? (
        <div className="space-y-4">
          {/* Drop zone */}
          <div
            className={`card p-8 border-2 border-dashed text-center cursor-pointer transition-all duration-150
              ${dragging ? 'border-brand-500 bg-brand-500/5' : 'border-slate-700 hover:border-slate-600'}`}
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
          >
            <input
              ref={inputRef}
              type="file"
              accept="image/jpeg,image/png"
              className="hidden"
              onChange={(e) => handleFile(e.target.files[0])}
            />
            {preview ? (
              <div className="space-y-3">
                <img
                  src={preview}
                  alt="Receipt preview"
                  className="max-h-64 mx-auto rounded-xl object-contain shadow-xl"
                />
                <p className="text-slate-400 text-sm">{file.name}</p>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-3 py-4">
                <div className="w-16 h-16 rounded-2xl bg-slate-800 flex items-center justify-center">
                  <ImageIcon size={32} className="text-slate-500" />
                </div>
                <div>
                  <p className="text-white font-medium">Drop your receipt here</p>
                  <p className="text-slate-500 text-sm mt-0.5">or click to browse · JPEG, PNG</p>
                </div>
              </div>
            )}
          </div>

          {error && (
            <div className="flex items-center gap-2 text-red-400 text-sm bg-red-900/20 border border-red-800/30 rounded-xl px-4 py-3">
              <XCircle size={16} />
              {error}
            </div>
          )}

          <div className="flex gap-3">
            <button
              onClick={handleUpload}
              disabled={!file || uploading}
              className="btn-primary flex-1 justify-center py-3"
            >
              {uploading ? (
                <>
                  <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Parsing receipt…
                </>
              ) : (
                <>
                  <Upload size={16} />
                  Parse &amp; Save Receipt
                </>
              )}
            </button>
            {file && (
              <button onClick={reset} className="btn-secondary px-4">
                Clear
              </button>
            )}
          </div>
        </div>
      ) : (
        /* ── Success result ──────────────────────────────────────────────── */
        <div className="space-y-4">
          <div className="card p-6 space-y-4">
            <div className="flex items-center gap-3">
              <CheckCircle2 size={28} className="text-green-400" />
              <div>
                <p className="font-semibold text-white">Receipt parsed successfully!</p>
                <p className="text-slate-400 text-sm">Expense saved to your records.</p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 pt-2">
              <InfoField label="Store" value={result.store} />
              <InfoField label="Total" value={`$${result.total.toFixed(2)}`} />
              <InfoField label="Date" value={result.date ? format(new Date(result.date), 'MMM d, yyyy') : '—'} />
              <InfoField label="Expense ID" value={`#${result.id}`} />
            </div>

            {result.items?.length > 0 && (
              <div>
                <p className="label mt-2">Extracted Items</p>
                <div className="bg-slate-800 rounded-xl overflow-hidden">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-700">
                        <th className="px-4 py-2.5 text-left text-slate-400 font-medium">Item</th>
                        <th className="px-4 py-2.5 text-right text-slate-400 font-medium">Price</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.items.map((item, i) => (
                        <tr key={i} className="border-b border-slate-700/50">
                          <td className="px-4 py-2 text-slate-300">{item.name}</td>
                          <td className="px-4 py-2 text-right text-brand-400 font-medium">
                            ${item.price.toFixed(2)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {result.notes && (
              <div>
                <p className="label">Raw OCR Text</p>
                <pre className="bg-slate-800 rounded-xl p-4 text-xs text-slate-400 whitespace-pre-wrap max-h-40 overflow-y-auto">
                  {result.notes}
                </pre>
              </div>
            )}
          </div>

          <button onClick={reset} className="btn-secondary w-full justify-center py-3">
            Upload Another Receipt
          </button>
        </div>
      )}
    </div>
  )
}

function InfoField({ label, value }) {
  return (
    <div className="bg-slate-800 rounded-xl p-3">
      <p className="text-xs text-slate-400 mb-0.5">{label}</p>
      <p className="font-semibold text-white">{value}</p>
    </div>
  )
}
