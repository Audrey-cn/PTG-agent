import Router from '@koa/router'
import * as ctrl from '../controllers/update'

export const updateRoutes = new Router()

updateRoutes.post('/api/prometheus/update', ctrl.handleUpdate)
