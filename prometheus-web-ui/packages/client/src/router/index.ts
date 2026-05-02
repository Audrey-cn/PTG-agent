import { createRouter, createWebHashHistory } from 'vue-router'
import { hasApiKey } from '@/api/client'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { public: true },
    },
    {
      path: '/prometheus/chat',
      name: 'prometheus.chat',
      component: () => import('@/views/prometheus/ChatView.vue'),
    },
    {
      path: '/prometheus/history',
      name: 'prometheus.history',
      component: () => import('@/views/prometheus/HistoryView.vue'),
    },
    {
      path: '/prometheus/jobs',
      name: 'prometheus.jobs',
      component: () => import('@/views/prometheus/JobsView.vue'),
    },
    {
      path: '/prometheus/models',
      name: 'prometheus.models',
      component: () => import('@/views/prometheus/ModelsView.vue'),
    },
    {
      path: '/prometheus/profiles',
      name: 'prometheus.profiles',
      component: () => import('@/views/prometheus/ProfilesView.vue'),
    },
    {
      path: '/prometheus/logs',
      name: 'prometheus.logs',
      component: () => import('@/views/prometheus/LogsView.vue'),
    },
    {
      path: '/prometheus/usage',
      name: 'prometheus.usage',
      component: () => import('@/views/prometheus/UsageView.vue'),
    },
    {
      path: '/prometheus/skills',
      name: 'prometheus.skills',
      component: () => import('@/views/prometheus/SkillsView.vue'),
    },
    {
      path: '/prometheus/memory',
      name: 'prometheus.memory',
      component: () => import('@/views/prometheus/MemoryView.vue'),
    },
    {
      path: '/prometheus/settings',
      name: 'prometheus.settings',
      component: () => import('@/views/prometheus/SettingsView.vue'),
    },
    {
      path: '/prometheus/gateways',
      name: 'prometheus.gateways',
      component: () => import('@/views/prometheus/GatewaysView.vue'),
    },
    {
      path: '/prometheus/channels',
      name: 'prometheus.channels',
      component: () => import('@/views/prometheus/ChannelsView.vue'),
    },
    {
      path: '/prometheus/terminal',
      name: 'prometheus.terminal',
      component: () => import('@/views/prometheus/TerminalView.vue'),
    },
    {
      path: '/prometheus/group-chat',
      name: 'prometheus.groupChat',
      component: () => import('@/views/prometheus/GroupChatView.vue'),
    },
    {
      path: '/prometheus/files',
      name: 'prometheus.files',
      component: () => import('@/views/prometheus/FilesView.vue'),
    },
  ],
})

router.beforeEach((to, _from, next) => {
  // Public pages don't need auth
  if (to.meta.public) {
    // Already has key, skip login
    if (to.name === 'login' && hasApiKey()) {
      next({ path: '/prometheus/chat' })
      return
    }
    next()
    return
  }

  // All other pages require token
  if (!hasApiKey()) {
    next({ name: 'login' })
    return
  }

  next()
})

export default router
