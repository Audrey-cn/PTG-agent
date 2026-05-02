import Router from '@koa/router'
import * as ctrl from '../../controllers/prometheus/nous-auth'

export const nousAuthRoutes = new Router()

nousAuthRoutes.post('/api/prometheus/auth/nous/start', ctrl.start)
nousAuthRoutes.get('/api/prometheus/auth/nous/poll/:sessionId', ctrl.poll)
nousAuthRoutes.get('/api/prometheus/auth/nous/status', ctrl.status)
