import Router from '@koa/router'
import * as ctrl from '../../controllers/prometheus/codex-auth'

export const codexAuthRoutes = new Router()

codexAuthRoutes.post('/api/prometheus/auth/codex/start', ctrl.start)
codexAuthRoutes.get('/api/prometheus/auth/codex/poll/:sessionId', ctrl.poll)
codexAuthRoutes.get('/api/prometheus/auth/codex/status', ctrl.status)
