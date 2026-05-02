import Router from '@koa/router'
import * as ctrl from '../../controllers/prometheus/memory'

export const memoryRoutes = new Router()

memoryRoutes.get('/api/prometheus/memory', ctrl.get)
memoryRoutes.post('/api/prometheus/memory', ctrl.save)
