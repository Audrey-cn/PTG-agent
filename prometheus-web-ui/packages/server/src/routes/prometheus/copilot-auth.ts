import Router from '@koa/router'
import * as ctrl from '../../controllers/prometheus/copilot-auth'

export const copilotAuthRoutes = new Router()

copilotAuthRoutes.post('/api/prometheus/auth/copilot/start', ctrl.start)
copilotAuthRoutes.get('/api/prometheus/auth/copilot/poll/:sessionId', ctrl.poll)
copilotAuthRoutes.get('/api/prometheus/auth/copilot/check-token', ctrl.checkToken)
copilotAuthRoutes.post('/api/prometheus/auth/copilot/enable', ctrl.enable)
copilotAuthRoutes.post('/api/prometheus/auth/copilot/disable', ctrl.disable)
