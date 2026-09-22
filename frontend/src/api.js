import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseKey = import.meta.env.VITE_SUPABASE_ANON_KEY

export const supabase = supabaseUrl && supabaseKey ? createClient(supabaseUrl, supabaseKey) : null

export const API_URL = import.meta.env.VITE_API_URL || ''

export async function api(path, { method = 'GET', token, body, form } = {}) {
  const headers = {}
  if (token) headers.Authorization = `Bearer ${token}`
  let payload
  if (form) {
    payload = form
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }
  const response = await fetch(`${API_URL}${path}`, { method, headers, body: payload })
  const text = await response.text()
  let data = null
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = { detail: text }
    }
  }
  if (!response.ok) {
    const message = Array.isArray(data?.detail)
      ? data.detail.map((d) => d.msg || d).join(' ')
      : data?.detail || 'The request failed.'
    const err = new Error(message)
    err.status = response.status
    err.payload = data
    throw err
  }
  return data
}

export function jobTypeLabel(value) {
  return { full_time: 'Full-time', part_time: 'Part-time', internship: 'Internship' }[value] || value
}

export function stageLabel(value) {
  return {
    applied: 'Applied',
    shortlisted: 'Shortlisted',
    interview: 'Interview',
    offer: 'Offer',
    hired: 'Hired',
    rejected: 'Rejected',
    withdrawn: 'Withdrawn',
  }[value] || value
}

export function formatDate(value) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return String(value)
  return d.toLocaleString()
}
