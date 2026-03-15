<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useFormBuilder } from '@/composables/useFormBuilder'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseBreadcrumb from '@/components/base/BaseBreadcrumb.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseAlert from '@/components/base/BaseAlert.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import BaseModal from '@/components/base/BaseModal.vue'
import TiptapEditor from '@/components/TiptapEditor.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import QuestionEditor from '@/components/forms/QuestionEditor.vue'
import FormPreview from '@/components/forms/FormPreview.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const {
  title,
  description,
  bannerUrl,
  deadline,
  maxRespondents,
  questions,
  isSchemaLocked,
  allowNonMembers,
  loading,
  saving,
  message,
  error,
  showPreview,
  sigName,
  breadcrumbSigId,
  previewMode,
  dragIndex,
  dropTargetIndex,
  showDraftBanner,
  isEdit,
  hasInvalidRating,
  minDeadline,
  draftTime,
  canUndo,
  canRedo,
  addQuestion,
  insertQuestionAt,
  removeQuestion,
  moveQuestion,
  duplicateQuestion,
  addOption,
  removeOption,
  moveOption,
  updateAllowedTypes,
  toggleCollapse,
  collapseAll,
  expandAll,
  isCollapsed,
  handleDragStart,
  handleDragOver,
  handleDragLeave,
  handleDrop,
  handleDragEnd,
  handleTouchStart,
  handleTouchMove,
  handleTouchEnd,
  handleUndo,
  handleRedo,
  restoreDraft,
  discardDraft,
  setPreviewDesktop,
  setPreviewMobile,
  uploadBanner,
  saveForm,
} = useFormBuilder({
  sigId: () => route.params.sigId as string,
  formId: () => route.params.formId as string,
  router,
  t,
})
</script>

<template>
  <div class="max-w-3xl mx-auto pb-24 overflow-x-hidden">
    <BaseBreadcrumb
      :items="[
        { label: t('breadcrumb.home'), to: '/' },
        { label: t('breadcrumb.sigs'), to: '/sigs' },
        {
          label: sigName || '...',
          to: breadcrumbSigId ? `/sigs/${breadcrumbSigId}` : '/sigs',
        },
        {
          label: t('breadcrumb.forms'),
          to: breadcrumbSigId ? `/sigs/${breadcrumbSigId}/forms` : '/sigs',
        },
        { label: isEdit ? title || t('forms.builder.editTitle') : t('forms.builder.createTitle') },
      ]"
    />

    <h1 class="text-2xl font-bold text-foreground mb-6">
      {{ isEdit ? t('forms.builder.editTitle') : t('forms.builder.createTitle') }}
    </h1>

    <SkeletonLoader v-if="loading" :lines="3" variant="card" />

    <template v-else>
      <!-- Draft restoration banner -->
      <BaseAlert v-if="showDraftBanner" type="warning" class="mb-4">
        <div class="flex flex-wrap items-center gap-2">
          <span>{{
            t('forms.builder.draftFound', {
              time: new Date(draftTime).toLocaleString(),
            })
          }}</span>
          <button class="text-sm font-medium text-brand-600 hover:underline" @click="restoreDraft">
            {{ t('forms.builder.draftRestore') }}
          </button>
          <button class="text-sm font-medium text-danger-500 hover:underline" @click="discardDraft">
            {{ t('forms.builder.draftDiscard') }}
          </button>
        </div>
      </BaseAlert>

      <BaseAlert v-if="message" type="success" class="mb-4">{{ message }}</BaseAlert>
      <BaseAlert v-if="error" type="error" class="mb-4">{{ error }}</BaseAlert>

      <BaseCard padding="lg" class="mb-6 space-y-4">
        <div>
          <label class="block text-sm font-medium text-foreground mb-1">{{
            t('forms.builder.bannerLabel')
          }}</label>
          <div v-if="bannerUrl" class="mb-2">
            <img
              :src="bannerUrl"
              alt="Banner"
              loading="lazy"
              class="w-full h-40 object-cover rounded-lg"
              width="768"
              height="160"
            />
          </div>
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp"
            @change="uploadBanner"
            class="text-sm text-muted"
          />
        </div>
        <BaseInput
          v-model="title"
          :label="t('forms.builder.titleLabel')"
          :placeholder="t('forms.builder.titlePlaceholder')"
        />
        <div>
          <label class="block text-sm font-medium text-foreground mb-1">{{
            t('forms.builder.descLabel')
          }}</label>
          <TiptapEditor v-model="description" />
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-foreground mb-1">{{
              t('forms.builder.deadlineLabel')
            }}</label>
            <input
              v-model="deadline"
              type="datetime-local"
              :min="minDeadline"
              class="w-full border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 text-foreground"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-foreground mb-1">{{
              t('forms.builder.maxRespondentsLabel')
            }}</label>
            <input
              v-model.number="maxRespondents"
              type="number"
              min="1"
              :placeholder="t('forms.builder.maxRespondentsPlaceholder')"
              class="w-full border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 text-foreground"
            />
          </div>
        </div>
        <label class="flex items-center gap-2 text-sm text-foreground mt-4">
          <input type="checkbox" v-model="allowNonMembers" class="rounded" />
          {{ t('forms.builder.allowNonMembers') }}
        </label>
        <p class="text-xs text-muted mt-1">
          {{ t('forms.builder.allowNonMembersHint') }}
        </p>
      </BaseCard>

      <div class="mb-6">
        <!-- Toolbar: title + actions -->
        <div class="flex flex-col sm:flex-row sm:items-center justify-between mb-3 gap-2">
          <h2 class="text-lg font-semibold text-foreground">
            {{ t('forms.builder.questionsTitle') }}
          </h2>
          <div class="flex items-center gap-2 flex-wrap">
            <!-- Undo/Redo buttons -->
            <button
              :disabled="!canUndo"
              :aria-label="t('forms.builder.undoBtn')"
              :title="t('forms.builder.undoBtn')"
              class="text-sm px-2 py-1 rounded border border-border text-muted hover:text-foreground disabled:opacity-30 transition"
              @click="handleUndo"
            >
              &#x21B6;
            </button>
            <button
              :disabled="!canRedo"
              :aria-label="t('forms.builder.redoBtn')"
              :title="t('forms.builder.redoBtn')"
              class="text-sm px-2 py-1 rounded border border-border text-muted hover:text-foreground disabled:opacity-30 transition"
              @click="handleRedo"
            >
              &#x21B7;
            </button>
            <!-- Collapse/Expand all -->
            <button
              v-if="questions.length > 1"
              class="text-sm px-2 py-1 rounded border border-border text-muted hover:text-foreground transition"
              :aria-label="t('forms.builder.collapseAllBtn')"
              @click="collapseAll"
            >
              {{ t('forms.builder.collapseAllBtn') }}
            </button>
            <button
              v-if="questions.length > 1"
              class="text-sm px-2 py-1 rounded border border-border text-muted hover:text-foreground transition"
              :aria-label="t('forms.builder.expandAllBtn')"
              @click="expandAll"
            >
              {{ t('forms.builder.expandAllBtn') }}
            </button>
            <BaseButton v-if="!isSchemaLocked" size="sm" @click="addQuestion">{{
              t('forms.builder.addQuestionBtn')
            }}</BaseButton>
          </div>
        </div>

        <BaseAlert v-if="isSchemaLocked" type="warning" class="mb-4">{{
          t('forms.builder.schemaLockedWarning')
        }}</BaseAlert>

        <div class="space-y-1">
          <QuestionEditor
            v-for="(q, i) in questions"
            :key="q.id"
            :question="q"
            :index="i"
            :total-questions="questions.length"
            :is-schema-locked="isSchemaLocked"
            :is-collapsed="isCollapsed(q.id)"
            :drag-index="dragIndex"
            :drop-target-index="dropTargetIndex"
            @remove="removeQuestion(i)"
            @move-up="moveQuestion(i, -1)"
            @move-down="moveQuestion(i, 1)"
            @duplicate="duplicateQuestion(i)"
            @toggle-collapse="toggleCollapse(q.id)"
            @add-option="addOption(q)"
            @remove-option="(oi: number) => removeOption(q, oi)"
            @move-option="(oi: number, dir: number) => moveOption(q, oi, dir)"
            @update-allowed-types="(event: Event) => updateAllowedTypes(q, event)"
            @insert-at="insertQuestionAt(i)"
            @drag-start="(e: DragEvent) => handleDragStart(e, i)"
            @drag-over="(e: DragEvent) => handleDragOver(e, i)"
            @drag-leave="handleDragLeave"
            @drop="(e: DragEvent) => handleDrop(e, i)"
            @drag-end="handleDragEnd"
            @touch-start="(e: TouchEvent) => handleTouchStart(e, i)"
            @touch-move="(e: TouchEvent) => handleTouchMove(e)"
            @touch-end="(e: TouchEvent) => handleTouchEnd(e)"
          />
        </div>
      </div>

      <div class="flex flex-col-reverse sm:flex-row justify-end gap-3">
        <BaseButton variant="secondary" size="lg" @click="showPreview = true">{{
          t('forms.builder.previewBtn')
        }}</BaseButton>
        <BaseButton size="lg" :loading="saving" :disabled="hasInvalidRating" @click="saveForm">{{
          isEdit ? t('forms.builder.updateBtn') : t('forms.builder.createBtn')
        }}</BaseButton>
      </div>
    </template>

    <!-- Floating Action Button -->
    <button
      v-if="!isSchemaLocked && !loading"
      class="fixed z-40 bg-brand-600 hover:bg-brand-700 text-white rounded-full shadow-lg flex items-center justify-center transition-all"
      style="
        bottom: calc(2rem + env(safe-area-inset-bottom, 0px));
        right: calc(2rem + env(safe-area-inset-right, 0px));
      "
      :class="['w-12 h-12 sm:w-auto sm:h-auto sm:px-4 sm:py-3']"
      :aria-label="t('forms.builder.addQuestionBtn')"
      @click="addQuestion"
    >
      <span class="text-xl leading-none sm:hidden">+</span>
      <span class="hidden sm:inline text-sm font-medium">{{
        t('forms.builder.addQuestionBtn')
      }}</span>
    </button>

    <!-- Preview modal -->
    <BaseModal v-model="showPreview" :title="title || t('forms.builder.createTitle')" size="xl">
      <FormPreview
        :title="title"
        :description="description"
        :banner-url="bannerUrl"
        :questions="questions"
        :preview-mode="previewMode"
        @set-desktop="setPreviewDesktop"
        @set-mobile="setPreviewMobile"
      />
    </BaseModal>
  </div>
</template>
