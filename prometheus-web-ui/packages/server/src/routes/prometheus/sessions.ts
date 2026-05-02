import Router from '@koa/router'
import * as ctrl from '../../controllers/prometheus/sessions'

export const sessionRoutes = new Router()

sessionRoutes.get('/api/prometheus/sessions/conversations', ctrl.listConversations)
sessionRoutes.get('/api/prometheus/sessions/conversations/:id/messages', ctrl.getConversationMessages)
sessionRoutes.get('/api/prometheus/sessions/conversations/:id/messages/paginated', ctrl.getConversationMessagesPaginated)
sessionRoutes.get('/api/prometheus/sessions', ctrl.list)
sessionRoutes.get('/api/prometheus/sessions/prometheus', ctrl.listPrometheusSessions)
sessionRoutes.get('/api/prometheus/sessions/prometheus/:id', ctrl.getPrometheusSession)
sessionRoutes.get('/api/prometheus/search/sessions', ctrl.search)
sessionRoutes.get('/api/prometheus/sessions/search', ctrl.search)
sessionRoutes.get('/api/prometheus/sessions/usage', ctrl.usageBatch)
sessionRoutes.get('/api/prometheus/usage/stats', ctrl.usageStats)
sessionRoutes.get('/api/prometheus/sessions/context-length', ctrl.contextLength)
sessionRoutes.get('/api/prometheus/sessions/:id', ctrl.get)
sessionRoutes.get('/api/prometheus/sessions/:id/usage', ctrl.usageSingle)
sessionRoutes.delete('/api/prometheus/sessions/:id', ctrl.remove)
sessionRoutes.post('/api/prometheus/sessions/:id/rename', ctrl.rename)
sessionRoutes.post('/api/prometheus/sessions/:id/workspace', ctrl.setWorkspace)
sessionRoutes.get('/api/prometheus/workspace/folders', ctrl.listWorkspaceFolders)
