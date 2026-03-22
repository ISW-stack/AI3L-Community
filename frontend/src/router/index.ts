import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import AdminLayout from '@/components/AdminLayout.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  scrollBehavior: (to) => (to.hash ? { el: to.hash } : { top: 0 }),
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
      meta: { requiresAuth: true, requiresMember: true },
    },
    {
      path: '/about/org-chart',
      name: 'about-org-chart',
      component: () => import('@/views/about/OrgChartView.vue'),
      meta: { requiresAuth: true, requiresMember: true },
    },
    {
      path: '/about/members',
      name: 'about-members',
      component: () => import('@/views/about/MembersView.vue'),
      meta: { requiresAuth: true, requiresMember: true },
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
      meta: { requiresAuth: true, fullWidth: true },
    },
    {
      path: '/users/:id',
      name: 'user-profile',
      component: () => import('@/views/UserProfileView.vue'),
      meta: { requiresAuth: true, fullWidth: true },
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
      meta: { requiresAuth: true, fullWidth: true },
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
      meta: { requiresAuth: true, requiresAdmin: true, fullWidth: true },
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
          path: 'contributors',
          name: 'admin-contributors',
          component: () => import('@/views/admin/ContributorsView.vue'),
          meta: { requiresSuperAdmin: true },
        },
        {
          path: 'audit-logs',
          name: 'admin-audit-logs',
          component: () => import('@/views/admin/AuditLogsView.vue'),
          meta: { requiresSuperAdmin: true },
        },
        {
          path: 'ip-bans',
          name: 'admin-ip-bans',
          component: () => import('@/views/admin/IpBansView.vue'),
          meta: { requiresSuperAdmin: true },
        },
        {
          path: 'site-settings',
          name: 'admin-site-settings',
          component: () => import('@/views/admin/SiteSettingsView.vue'),
          meta: { requiresSuperAdmin: true },
        },
      ],
    },
    // Forms directory & standalone create (before /forms/:formId)
    {
      path: '/forms',
      name: 'forms',
      component: () => import('@/views/forms/FormsDirectoryView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/forms/new',
      name: 'standalone-form-create',
      component: () => import('@/views/forms/FormBuilderView.vue'),
      meta: { requiresAuth: true, requiresMember: true },
    },
    // Albums
    {
      path: '/albums',
      name: 'albums',
      component: () => import('@/views/albums/AlbumsDirectoryView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/albums/create',
      name: 'album-create',
      component: () => import('@/views/albums/AlbumCreateView.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/albums/:id',
      component: () => import('@/views/albums/AlbumLayout.vue'),
      meta: { requiresAuth: true, fullWidth: true },
      children: [
        { path: '', redirect: { name: 'album-photos' } },
        {
          path: 'photos',
          name: 'album-photos',
          component: () => import('@/views/albums/AlbumPhotosView.vue'),
        },
        {
          path: 'members',
          name: 'album-members',
          component: () => import('@/views/albums/AlbumMembersView.vue'),
        },
        {
          path: 'comments',
          name: 'album-comments',
          component: () => import('@/views/albums/AlbumCommentsView.vue'),
        },
      ],
    },
    // Messages (DM)
    {
      path: '/messages',
      name: 'messages',
      component: () => import('@/views/DMView.vue'),
      meta: { requiresAuth: true, requiresMember: true, fullWidth: true },
    },
    {
      path: '/messages/:userId',
      name: 'dm-user',
      component: () => import('@/views/DMView.vue'),
      meta: { requiresAuth: true, requiresMember: true, fullWidth: true },
    },
    // Social
    {
      path: '/friends',
      name: 'friends',
      component: () => import('@/views/social/FriendsView.vue'),
      meta: { requiresAuth: true, requiresMember: true },
    },
    {
      path: '/following',
      name: 'following',
      component: () => import('@/views/social/FollowingView.vue'),
      meta: { requiresAuth: true, requiresMember: true },
    },
    {
      path: '/blocked-users',
      name: 'blocked-users',
      component: () => import('@/views/social/BlockedUsersView.vue'),
      meta: { requiresAuth: true, requiresMember: true },
    },
    // Q&A
    {
      path: '/qa',
      name: 'qa',
      component: () => import('@/views/qa/QAListView.vue'),
      meta: { requiresAuth: true, fullWidth: true },
    },
    {
      path: '/qa/ask',
      name: 'qa-ask',
      component: () => import('@/views/qa/QACreateView.vue'),
      meta: { requiresAuth: true, requiresMember: true },
    },
    {
      path: '/qa/:id',
      name: 'qa-detail',
      component: () => import('@/views/qa/QADetailView.vue'),
      meta: { requiresAuth: true },
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
      component: () => import('@/views/sigs/SigLayout.vue'),
      meta: { requiresAuth: true, fullWidth: true },
      children: [
        { path: '', redirect: { name: 'sig-posts' } },
        {
          path: 'posts',
          name: 'sig-posts',
          component: () => import('@/views/sigs/SigPostsView.vue'),
        },
        {
          path: 'members',
          name: 'sig-members',
          component: () => import('@/views/sigs/SigMembersView.vue'),
        },
        {
          path: 'forms',
          name: 'sig-forms',
          component: () => import('@/views/sigs/SigFormsView.vue'),
        },
      ],
    },
    {
      path: '/sigs/:sigId/forms/new',
      name: 'form-create',
      component: () => import('@/views/forms/FormBuilderView.vue'),
      meta: { requiresAuth: true, requiresMember: true },
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
      meta: { requiresAuth: true, requiresMember: true },
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
  const toast = useToastStore()

  // Redirect authenticated users away from guest-only pages
  if (to.meta.guest && auth.isAuthenticated) {
    return { name: 'home' }
  }

  // Redirect unauthenticated users to login
  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  // Block guest users from member-only pages
  if (to.meta.requiresMember && auth.isGuest) {
    toast.show('You must be a full member to access that page.', 'error')
    return { name: 'home' }
  }

  // Check admin access
  if (to.meta.requiresAdmin && !auth.isAdmin) {
    toast.show('You do not have permission to access that page.', 'error')
    return { name: 'home' }
  }

  // Check super admin access
  if (to.meta.requiresSuperAdmin && !auth.isSuperAdmin) {
    toast.show('You do not have permission to access that page.', 'error')
    return { name: 'home' }
  }
})

export default router
