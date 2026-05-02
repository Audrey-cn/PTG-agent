import Router from '@koa/router'
import * as ctrl from '../../controllers/prometheus/gateways'

export const gatewayRoutes = new Router()

gatewayRoutes.get('/api/prometheus/gateways', ctrl.list)
gatewayRoutes.post('/api/prometheus/gateways/:name/start', ctrl.start)
gatewayRoutes.post('/api/prometheus/gateways/:name/stop', ctrl.stop)
gatewayRoutes.get('/api/prometheus/gateways/:name/health', ctrl.health)
