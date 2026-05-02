import Router from '@koa/router'
import * as ctrl from '../../controllers/prometheus/logs'

export const logRoutes = new Router()

logRoutes.get('/api/prometheus/logs', ctrl.list)
logRoutes.get('/api/prometheus/logs/:name', ctrl.read)
