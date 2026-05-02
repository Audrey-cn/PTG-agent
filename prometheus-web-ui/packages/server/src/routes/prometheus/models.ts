import Router from '@koa/router'
import * as ctrl from '../../controllers/prometheus/models'

export const modelRoutes = new Router()

modelRoutes.get('/api/prometheus/available-models', ctrl.getAvailable)
modelRoutes.get('/api/prometheus/config/models', ctrl.getConfigModels)
modelRoutes.put('/api/prometheus/config/model', ctrl.setConfigModel)
