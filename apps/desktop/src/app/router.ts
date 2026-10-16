import { createRouter, createWebHashHistory } from 'vue-router'

export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/chat' },
    {
      path: '/chat',
      meta: { workspace: 'chat' },
      component: () => import('../modules/chat/pages/ChatPage.vue'),
    },
    {
      path: '/coding',
      meta: { workspace: 'coding' },
      component: () => import('../modules/coding/pages/CodingPage.vue'),
    },
    {
      path: '/coding/projects/:projectId/sessions/:sessionId',
      meta: { workspace: 'coding' },
      component: () => import('../modules/coding/pages/CodingPage.vue'),
    },
    { path: '/models', component: () => import('../modules/models/pages/ModelsPage.vue') },
    {
      path: '/image-studio',
      component: () => import('../modules/image-studio/pages/ImageStudioPage.vue'),
    },
    { path: '/settings', component: () => import('../modules/settings/pages/SettingsPage.vue') },
  ],
})
