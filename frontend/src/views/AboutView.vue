<script setup lang="ts">
interface Contributor {
  name: string
  role: string
  github?: string
}

const contributors: Contributor[] = [
  { name: 'Alice Chen', role: 'Project Lead & Backend', github: 'alicecodes' },
  { name: 'Bob Johnson', role: 'Frontend Lead', github: 'bobjohnson' },
  { name: 'Carol Smith', role: 'Database & DevOps', github: 'carolsmith' },
  { name: 'David Lee', role: 'UI/UX Designer', github: 'davidlee' },
  { name: 'Emma Wilson', role: 'QA & Testing', github: 'emmawilson' },
  { name: 'Frank Brown', role: 'Documentation', github: 'frankbrown' },
]

function getGitHubUrl(username: string): string {
  return `https://github.com/${username}`
}
</script>

<template>
  <div class="max-w-6xl mx-auto px-4 py-8">
    <!-- Header Section -->
    <div class="mb-12">
      <h1 class="text-4xl font-bold text-foreground mb-4">Platform Contributors</h1>
      <p class="text-lg text-muted max-w-2xl">
        The AI3L Community platform was designed and built by a talented team of developers,
        designers, and advocates committed to fostering collaborative learning and research. This
        project represents our shared vision of creating an inclusive space for knowledge exchange
        and community engagement.
      </p>
    </div>

    <!-- Contributors Grid -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      <div
        v-for="contributor in contributors"
        :key="contributor.name"
        class="bg-surface border border-border rounded-lg p-6 hover:shadow-lg transition-shadow"
      >
        <h3 class="text-lg font-semibold text-foreground mb-2">{{ contributor.name }}</h3>
        <p class="text-sm text-muted mb-4">{{ contributor.role }}</p>
        <a
          v-if="contributor.github"
          :href="getGitHubUrl(contributor.github)"
          target="_blank"
          rel="noopener noreferrer"
          class="inline-flex items-center text-sm text-brand-600 hover:text-brand-700 font-medium transition"
        >
          @{{ contributor.github }}
          <span class="ml-1">↗</span>
        </a>
      </div>
    </div>

    <!-- Additional Info Section -->
    <div class="mt-16 pt-8 border-t border-border">
      <h2 class="text-2xl font-semibold text-foreground mb-4">About this Project</h2>
      <p class="text-muted mb-4">
        AI3L Community is built on modern technologies including Vue 3, FastAPI, and PostgreSQL.
        We are committed to maintaining high code quality, security, and accessibility standards.
      </p>
      <p class="text-muted">
        If you're interested in contributing to this project, please refer to our contributor
        guidelines in the repository.
      </p>
    </div>
  </div>
</template>
