import Router from '@koa/router'
import * as ctrl from '../../controllers/prometheus/providers'

export const providerRoutes = new Router()

providerRoutes.post('/api/prometheus/config/providers', ctrl.create)
providerRoutes.put('/api/prometheus/config/providers/:poolKey', ctrl.update)
providerRoutes.delete('/api/prometheus/config/providers/:poolKey', ctrl.remove)
