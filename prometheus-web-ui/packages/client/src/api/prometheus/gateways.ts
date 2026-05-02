import { request } from '../client'

export interface GatewayStatus {
  profile: string
  port: number
  host: string
  url: string
  running: boolean
  pid?: number
}

export async function fetchGateways(): Promise<GatewayStatus[]> {
  const res = await request<{ gateways: GatewayStatus[] }>('/api/prometheus/gateways')
  return res.gateways
}

export async function startGateway(name: string): Promise<GatewayStatus> {
  const res = await request<{ success: boolean; gateway: GatewayStatus }>(`/api/prometheus/gateways/${name}/start`, { method: 'POST' })
  return res.gateway
}

export async function stopGateway(name: string): Promise<void> {
  await request(`/api/prometheus/gateways/${name}/stop`, { method: 'POST' })
}

export async function checkGatewayHealth(name: string): Promise<GatewayStatus> {
  const res = await request<{ gateway: GatewayStatus }>(`/api/prometheus/gateways/${name}/health`)
  return res.gateway
}
