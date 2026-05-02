import Router from '@koa/router'
import * as ctrl from '../../controllers/prometheus/profiles'

export const profileRoutes = new Router()

profileRoutes.get('/api/prometheus/profiles', ctrl.list)
profileRoutes.post('/api/prometheus/profiles', ctrl.create)
profileRoutes.get('/api/prometheus/profiles/:name', ctrl.get)
profileRoutes.delete('/api/prometheus/profiles/:name', ctrl.remove)
profileRoutes.post('/api/prometheus/profiles/:name/rename', ctrl.rename)
profileRoutes.put('/api/prometheus/profiles/active', ctrl.switchProfile)
profileRoutes.post('/api/prometheus/profiles/:name/export', ctrl.exportProfile)
profileRoutes.post('/api/prometheus/profiles/import', ctrl.importProfile)
