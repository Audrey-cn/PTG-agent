import type { Context, Next } from 'koa'

// Shared route modules
import { healthRoutes } from './health'
import { webhookRoutes } from './webhook'
import { uploadRoutes } from './upload'
import { updateRoutes } from './update'
import { authPublicRoutes, authProtectedRoutes } from './auth'

// Prometheus route modules
import { sessionRoutes } from './prometheus/sessions'
import { profileRoutes } from './prometheus/profiles'
import { skillRoutes } from './prometheus/skills'
import { memoryRoutes } from './prometheus/memory'
import { modelRoutes } from './prometheus/models'
import { providerRoutes } from './prometheus/providers'
import { configRoutes } from './prometheus/config'
import { logRoutes } from './prometheus/logs'
import { codexAuthRoutes } from './prometheus/codex-auth'
import { nousAuthRoutes } from './prometheus/nous-auth'
import { copilotAuthRoutes } from './prometheus/copilot-auth'
import { gatewayRoutes } from './prometheus/gateways'
import { weixinRoutes } from './prometheus/weixin'
import { fileRoutes } from './prometheus/files'
import { downloadRoutes } from './prometheus/download'
import { jobRoutes } from './prometheus/jobs'
import { cronHistoryRoutes } from './prometheus/cron-history'
import { proxyRoutes, proxyMiddleware } from './prometheus/proxy'
import { groupChatRoutes, setGroupChatServer } from './prometheus/group-chat'

/**
 * Register all routes on the Koa app.
 * Public routes are registered first, then auth middleware,
 * then all protected routes. Returns the proxy middleware (must be mounted last).
 */
export function registerRoutes(app: any, requireAuth: (ctx: Context, next: Next) => Promise<void>) {
  // --- Public routes (no auth required) ---
  app.use(healthRoutes.routes())
  app.use(webhookRoutes.routes())
  app.use(authPublicRoutes.routes())

  // --- Auth middleware: all routes below require authentication ---
  app.use(requireAuth)

  // --- Protected routes (auth required) ---
  app.use(authProtectedRoutes.routes())
  app.use(uploadRoutes.routes())
  app.use(updateRoutes.routes())           // Must be before proxy (proxy catch-all matches everything)
  app.use(sessionRoutes.routes())
  app.use(profileRoutes.routes())
  app.use(skillRoutes.routes())
  app.use(memoryRoutes.routes())
  app.use(modelRoutes.routes())
  app.use(providerRoutes.routes())
  app.use(configRoutes.routes())
  app.use(logRoutes.routes())
  app.use(codexAuthRoutes.routes())
  app.use(nousAuthRoutes.routes())
  app.use(copilotAuthRoutes.routes())
  app.use(gatewayRoutes.routes())
  app.use(weixinRoutes.routes())
  app.use(groupChatRoutes.routes())       // Must be before proxy
  app.use(fileRoutes.routes())              // Must be before proxy (proxy catch-all matches everything)
  app.use(downloadRoutes.routes())          // Must be before proxy
  app.use(jobRoutes.routes())               // Must be before proxy
  app.use(cronHistoryRoutes.routes())        // Must be before proxy
  app.use(proxyRoutes.routes())

  // Proxy catch-all middleware (must be last)
  return proxyMiddleware
}
