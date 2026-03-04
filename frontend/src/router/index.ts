import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import AdminLayout from '@/components/AdminLayout.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('@/views/HomeView.vue'),
    },
    {
      path: '/about',
      name: 'about',
      component: () => import('@/views/AboutView.vue'),
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { guest: true },
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('@/views/RegisterView.vue'),
      meta: { guest: true },
    },
    {
      path: '/guest',
      name: 'guest-login',
      component: () => import('@/views/GuestLoginView.vue'),
      meta: { guest: true },
    },
    {
      path: '/profile',
      name: 'profile',
      component: () => import('@/views/ProfileView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/users/:id',
      name: 'user-profile',
      component: () => import('@/views/UserProfileView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/notifications',
      name: 'notifications',
      component: () => import('@/views/NotificationsView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/forum',
      name: 'forum',
      component: () => import('@/views/forum/ForumView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/forum/create',
      name: 'forum-create',
      component: () => import('@/views/forum/PostCreateView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/forum/:id',
      name: 'forum-post',
      component: () => import('@/views/forum/PostDetailView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/admin',
      component: AdminLayout,
      meta: { requiresAuth: true, requiresAdmin: true },
      children: [
        {
          path: '',
          name: 'admin-dashboard',
          component: () => import('@/views/admin/AdminDashboardView.vue'),
        },
        {
          path: 'users',
          name: 'admin-users',
          component: () => import('@/views/admin/UsersView.vue'),
        },
        {
          path: 'applications',
          name: 'admin-applications',
          component: () => import('@/views/admin/ApplicationsView.vue'),
        },
        {
          path: 'reports',
          name: 'admin-reports',
          component: () => import('@/views/admin/ReportsView.vue'),
        },
        {
          path: 'categories',
          name: 'admin-categories',
          component: () => import('@/views/admin/CategoriesView.vue'),
        },
        {
          path: 'invite-codes',
          name: 'admin-invite-codes',
          component: () => import('@/views/admin/InviteCodesView.vue'),
        },
        {
          path: 'audit-logs',
          name: 'admin-audit-logs',
          component: () => import('@/views/admin/AuditLogsView.vue'),
          meta: { requiresSuperAdmin: true },
        },
      ],
    },
    {
      path: '/sigs',
      name: 'sigs',
      component: () => import('@/views/sigs/SigsDirectoryView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/sigs/create',
      name: 'sig-create',
      component: () => import('@/views/sigs/SigCreateView.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/sigs/:id',
      name: 'sig-detail',
      component: () => import('@/views/sigs/SigDetailView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/sigs/:sigId/forms/new',
      name: 'form-create',
      component: () => import('@/views/forms/FormBuilderView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/forms/:formId',
      name: 'form-view',
      component: () => import('@/views/forms/FormView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/forms/:formId/edit',
      name: 'form-edit',
      component: () => import('@/views/forms/FormBuilderView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('@/views/NotFoundView.vue'),
    },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()

  // Redirect authenticated users away from guest-only pages
  if (to.meta.guest && auth.isAuthenticated) {
    return { name: 'home' }
  }

  // Redirect unauthenticated users to login
  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  // Check admin access
  if (to.meta.requiresAdmin && !auth.isAdmin) {
    return { name: 'home' }
  }

  // Check super admin access
  if (to.meta.requiresSuperAdmin && !auth.isSuperAdmin) {
    return { name: 'home' }
  }
})

export default router
