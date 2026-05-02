import Router from '@koa/router'
import * as ctrl from '../../controllers/prometheus/weixin'

export const weixinRoutes = new Router()

weixinRoutes.get('/api/prometheus/weixin/qrcode', ctrl.getQrcode)
weixinRoutes.get('/api/prometheus/weixin/qrcode/status', ctrl.pollStatus)
weixinRoutes.post('/api/prometheus/weixin/save', ctrl.save)
