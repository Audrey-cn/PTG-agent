import Router from '@koa/router'
import * as ctrl from '../../controllers/prometheus/config'

export const configRoutes = new Router()

configRoutes.get('/api/prometheus/config', ctrl.getConfig)
configRoutes.put('/api/prometheus/config', ctrl.updateConfig)
configRoutes.put('/api/prometheus/config/credentials', ctrl.updateCredentials)
