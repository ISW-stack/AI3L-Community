<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
</script>

<template>
  <div class="max-w-4xl mx-auto py-12 px-4">
    <div class="text-center space-y-4 mb-12">
      <h1 class="text-4xl font-bold text-gray-900">AI3L Community</h1>
      <p class="text-lg text-gray-600">AI in Language Learning and Literacy - Academic Exchange Platform</p>
    </div>

    <!-- Authenticated view -->
    <div v-if="auth.isAuthenticated" class="space-y-6">
      <div class="bg-white rounded-xl shadow p-6">
        <h2 class="text-xl font-semibold text-gray-900 mb-2">
          {{ auth.isGuest ? 'Welcome, Guest' : `Welcome back, ${auth.user?.display_name}` }}
        </h2>
        <p class="text-gray-600">Explore discussions and share your research.</p>
        <router-link to="/forum" class="inline-block mt-3 text-sm text-blue-600 hover:underline font-medium">
          Browse Forum &rarr;
        </router-link>
      </div>

      <div v-if="auth.isGuest" class="bg-yellow-50 border border-yellow-200 rounded-xl p-4 text-sm text-yellow-700">
        You are browsing as a guest. Your session lasts 45 minutes.
        <router-link to="/register" class="font-medium underline">Sign up</router-link>
        for full access.
      </div>
    </div>

    <!-- Unauthenticated view -->
    <div v-else class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <router-link to="/login" class="bg-white rounded-xl shadow p-6 hover:shadow-md transition text-center">
        <div class="text-3xl mb-2">🔑</div>
        <h3 class="font-semibold text-gray-900">Log In</h3>
        <p class="text-sm text-gray-500 mt-1">Sign in with your credentials</p>
      </router-link>

      <router-link to="/register" class="bg-white rounded-xl shadow p-6 hover:shadow-md transition text-center">
        <div class="text-3xl mb-2">📝</div>
        <h3 class="font-semibold text-gray-900">Sign Up</h3>
        <p class="text-sm text-gray-500 mt-1">Create a new account</p>
      </router-link>

      <router-link to="/guest" class="bg-white rounded-xl shadow p-6 hover:shadow-md transition text-center">
        <div class="text-3xl mb-2">👀</div>
        <h3 class="font-semibold text-gray-900">Guest Access</h3>
        <p class="text-sm text-gray-500 mt-1">Browse without signing up</p>
      </router-link>
    </div>
  </div>
</template>
