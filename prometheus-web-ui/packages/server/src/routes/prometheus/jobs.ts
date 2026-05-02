import Router from '@koa/router'
import * as ctrl from '../../controllers/prometheus/jobs'

export const jobRoutes = new Router()

jobRoutes.get('/api/prometheus/jobs', ctrl.list)
jobRoutes.get('/api/prometheus/jobs/:id', ctrl.get)
jobRoutes.post('/api/prometheus/jobs', ctrl.create)
jobRoutes.patch('/api/prometheus/jobs/:id', ctrl.update)
jobRoutes.delete('/api/prometheus/jobs/:id', ctrl.remove)
jobRoutes.post('/api/prometheus/jobs/:id/pause', ctrl.pause)
jobRoutes.post('/api/prometheus/jobs/:id/resume', ctrl.resume)
jobRoutes.post('/api/prometheus/jobs/:id/run', ctrl.run)
