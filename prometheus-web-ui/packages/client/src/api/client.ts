import router from '@/router'

const DEFAULT_BASE_URL = ''

function getBaseUrl(): string {
  return localStorage.getItem('prometheus_server_url') || DEFAULT_BASE_URL
}

export function getApiKey(): string {
  return localStorage.getItem('prometheus_api_key') || ''
}

export function setServerUrl(url: string) {
  localStorage.setItem('prometheus_server_url', url)
}

export function setApiKey(key: string) {
  localStorage.setItem('prometheus_api_key', key)
}

export function clearApiKey() {
  localStorage.removeItem('prometheus_api_key')
}

export function hasApiKey(): boolean {
  return !!getApiKey()
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const base = getBaseUrl()
  const url = `${base}${path}`
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...options.headers as Record<string, string>,
  }

  const apiKey = getApiKey()
  if (apiKey) {
    headers['Authorization'] = `Bearer ${apiKey}`
  }

  // Inject active profile header for proxied gateway requests
  const profileName = localStorage.getItem('prometheus_active_profile_name')
  if (profileName && profileName !== 'default') {
    headers['X-Prometheus-Profile'] = profileName
  }

  const res = await fetch(url, { ...options, headers })

  // Global 401 handler — only redirect to login for local BFF endpoints
  // Proxied gateway requests should not trigger logout
  const isLocalBff = !path.startsWith('/api/prometheus/v1/') &&
    !path.startsWith('/api/prometheus/jobs') &&
    !path.startsWith('/api/prometheus/skills')

  if (res.status === 401 && isLocalBff) {
    clearApiKey()
    if (router.currentRoute.value.name !== 'login') {
      router.replace({ name: 'login' })
    }
    throw new Error('Unauthorized')
  }

  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`API Error ${res.status}: ${text || res.statusText}`)
  }

  return res.json()
}

export function getBaseUrlValue(): string {
  return getBaseUrl()
}
