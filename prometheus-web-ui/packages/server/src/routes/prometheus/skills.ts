import Router from '@koa/router'
import * as ctrl from '../../controllers/prometheus/skills'

export const skillRoutes = new Router()

skillRoutes.get('/api/prometheus/skills', ctrl.list)
skillRoutes.put('/api/prometheus/skills/toggle', ctrl.toggle)
skillRoutes.put('/api/prometheus/skills/pin', ctrl.pin_)
skillRoutes.get('/api/prometheus/skills/:category/:skill/files', ctrl.listFiles)
skillRoutes.get('/api/prometheus/skills/{*path}', ctrl.readFile_)
