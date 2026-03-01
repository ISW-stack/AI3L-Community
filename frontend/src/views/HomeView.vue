<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseAlert from '@/components/base/BaseAlert.vue'
import { KeyRound, PenTool, GraduationCap } from 'lucide-vue-next'

const auth = useAuthStore()
</script>

<template>
  <div class="max-w-4xl mx-auto">
    <!-- Authenticated view -->
    <div v-if="auth.isAuthenticated" class="space-y-6">
      <BaseCard padding="lg">
        <h2 class="text-xl font-semibold text-foreground mb-2">
          {{ auth.isGuest ? 'Welcome, Guest' : `Welcome back, ${auth.user?.display_name}` }}
        </h2>
        <p class="text-muted">Explore discussions and share your research.</p>
        <div class="mt-4 flex flex-wrap gap-3">
          <router-link to="/forum">
            <BaseButton>Browse Forum</BaseButton>
          </router-link>
          <router-link to="/sigs">
            <BaseButton variant="secondary">My SIGs</BaseButton>
          </router-link>
        </div>
      </BaseCard>

      <BaseAlert v-if="auth.isGuest" type="warning">
        You are browsing as a guest. Your session lasts 45 minutes.
        <router-link to="/register" class="font-medium underline">Sign up</router-link>
        for full access.
      </BaseAlert>
    </div>

    <!-- Unauthenticated view -->
    <div v-else>
      <!-- Hero Section -->
      <div class="bg-gradient-to-br from-brand-900 to-brand-700 rounded-lg p-8 sm:p-12 text-white text-center mb-8">
        <h1 class="text-3xl sm:text-4xl font-bold mb-3">AI3L Community</h1>
        <p class="text-brand-200 text-lg mb-6">AI in Language Learning and Literacy &mdash; Academic Exchange Platform</p>
        <div class="flex flex-wrap items-center justify-center gap-3">
          <router-link to="/register">
            <button class="inline-flex items-center justify-center px-6 py-3 text-base font-semibold rounded-lg bg-white text-brand-900 hover:bg-brand-50 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white">
              Get Started
            </button>
          </router-link>
          <router-link to="/guest">
            <button class="inline-flex items-center justify-center px-6 py-3 text-base font-semibold rounded-lg text-white/90 hover:text-white hover:bg-white/10 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white">
              Browse as Guest
            </button>
          </router-link>
        </div>
      </div>

      <!-- Feature cards -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <router-link to="/login" class="block">
          <BaseCard hoverable padding="lg" class="text-center h-full">
            <div class="inline-flex items-center justify-center w-12 h-12 rounded-lg bg-brand-50 text-brand-600 mb-3">
              <KeyRound class="w-6 h-6" aria-hidden="true" />
            </div>
            <h3 class="font-semibold text-foreground">Log In</h3>
            <p class="text-sm text-muted mt-1">Sign in with your credentials</p>
          </BaseCard>
        </router-link>

        <router-link to="/register" class="block">
          <BaseCard hoverable padding="lg" class="text-center h-full">
            <div class="inline-flex items-center justify-center w-12 h-12 rounded-lg bg-brand-50 text-brand-600 mb-3">
              <PenTool class="w-6 h-6" aria-hidden="true" />
            </div>
            <h3 class="font-semibold text-foreground">Sign Up</h3>
            <p class="text-sm text-muted mt-1">Create a new account</p>
          </BaseCard>
        </router-link>

        <router-link to="/guest" class="block">
          <BaseCard hoverable padding="lg" class="text-center h-full">
            <div class="inline-flex items-center justify-center w-12 h-12 rounded-lg bg-brand-50 text-brand-600 mb-3">
              <GraduationCap class="w-6 h-6" aria-hidden="true" />
            </div>
            <h3 class="font-semibold text-foreground">Guest Access</h3>
            <p class="text-sm text-muted mt-1">Browse without signing up</p>
          </BaseCard>
        </router-link>
      </div>
    </div>
  </div>
</template>
