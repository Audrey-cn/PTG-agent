let gatewayManager: any = null

export function getGatewayManagerInstance(): any {
  return gatewayManager
}

export async function initGatewayManager(): Promise<void> {
  const { GatewayManager } = await import('./prometheus/gateway-manager')
  const { getActiveProfileName } = await import('./prometheus/prometheus-profile')
  const activeProfile = getActiveProfileName()
  gatewayManager = new GatewayManager(activeProfile)

  await gatewayManager.detectAllOnStartup()
  await gatewayManager.startAll()
  console.log("startall")
}
