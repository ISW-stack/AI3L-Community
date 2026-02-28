<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const displayName = ref('')
const error = ref('')
const loading = ref(false)

const passwordChecks = computed(() => ({
  length: password.value.length >= 8,
  upper: /[A-Z]/.test(password.value),
  lower: /[a-z]/.test(password.value),
  digit: /[0-9]/.test(password.value),
}))

const passwordValid = computed(
  () => passwordChecks.value.length && passwordChecks.value.upper && passwordChecks.value.lower && passwordChecks.value.digit,
)

const passwordsMatch = computed(() => password.value === confirmPassword.value && password.value.length > 0)

async function handleRegister() {
  if (!passwordValid.value) {
    error.value = 'Password does not meet the security requirements.'
    return
  }
  if (!passwordsMatch.value) {
    error.value = 'Passwords do not match.'
    return
  }

  error.value = ''
  loading.value = true
  try {
    await auth.register(username.value, password.value, displayName.value)
    router.push('/')
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Registration failed. Please try again.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-50 px-4">
    <div class="w-full max-w-md bg-white rounded-xl shadow-lg p-8">
      <h1 class="text-2xl font-bold text-center text-gray-900 mb-6">Create an Account</h1>

      <div v-if="error" class="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 mb-4 text-sm">
        {{ error }}
      </div>

      <form @submit.prevent="handleRegister" class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Username</label>
          <input
            v-model="username"
            type="text"
            required
            minlength="3"
            maxlength="50"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
            placeholder="3-50 characters"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Display Name</label>
          <input
            v-model="displayName"
            type="text"
            required
            maxlength="100"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Password</label>
          <input
            v-model="password"
            type="password"
            required
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
          />
          <ul class="mt-2 text-xs space-y-1">
            <li :class="passwordChecks.length ? 'text-green-600' : 'text-gray-400'">At least 8 characters</li>
            <li :class="passwordChecks.upper ? 'text-green-600' : 'text-gray-400'">Contains an uppercase letter</li>
            <li :class="passwordChecks.lower ? 'text-green-600' : 'text-gray-400'">Contains a lowercase letter</li>
            <li :class="passwordChecks.digit ? 'text-green-600' : 'text-gray-400'">Contains a digit</li>
          </ul>
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Confirm Password</label>
          <input
            v-model="confirmPassword"
            type="password"
            required
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
          />
          <p v-if="confirmPassword && !passwordsMatch" class="text-red-500 text-xs mt-1">Passwords do not match</p>
        </div>

        <button
          type="submit"
          :disabled="loading || !passwordValid || !passwordsMatch"
          class="w-full bg-blue-600 text-white py-2.5 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
        >
          {{ loading ? 'Signing up...' : 'Sign Up' }}
        </button>
      </form>

      <p class="mt-6 text-center text-sm text-gray-500">
        Already have an account?
        <router-link to="/login" class="text-blue-600 hover:underline">Log In</router-link>
      </p>
    </div>
  </div>
</template>
