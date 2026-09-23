import { createRouter, createWebHashHistory } from 'vue-router'

export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/chat' },
    { path: '/chat', component: () => import('../modules/chat/pages/ChatPage.vue') },
    { path: '/models', component: () => import('../modules/models/pages/ModelsPage.vue') },
    { path: '/image-studio', component: () => import('../modules/image-studio/pages/ImageStudioPage.vue') },
    { path: '/settings', component: () => import('../modules/settings/pages/SettingsPage.vue') },
  ],
})
