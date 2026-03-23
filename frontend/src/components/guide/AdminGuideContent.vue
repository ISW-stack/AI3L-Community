<script setup lang="ts">
import BaseAlert from '@/components/base/BaseAlert.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
</script>

<template>
  <div v-if="auth.isAdmin" class="guide-content space-y-10">
    <BaseAlert type="info" class="mb-2">
      This guide covers <strong>additional</strong> features beyond what Members have. Read the
      <strong>Guest Guide</strong> and <strong>Member Guide</strong> tabs first.
    </BaseAlert>

    <!-- Admin Panel Overview -->
    <section id="admin-panel-overview">
      <h2 class="text-xl font-bold text-foreground pb-2 border-b border-border mb-4">
        Admin Panel Overview
      </h2>
      <p class="text-sm text-foreground/80 mb-3">
        Access the Admin Panel from the <strong>Admin</strong> dropdown in the navbar. The admin
        area uses a dedicated sidebar layout.
      </p>
      <div class="overflow-x-auto">
        <table class="w-full text-sm border border-border rounded-lg overflow-hidden">
          <thead class="bg-surface-alt">
            <tr>
              <th class="text-left px-4 py-2 font-medium text-foreground">Page</th>
              <th class="text-left px-4 py-2 font-medium text-foreground">Purpose</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border">
            <tr>
              <td class="px-4 py-2 font-medium">Dashboard</td>
              <td class="px-4 py-2 text-foreground/80">Overview statistics and quick navigation</td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium">Users</td>
              <td class="px-4 py-2 text-foreground/80">Manage all user accounts</td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium">Applications</td>
              <td class="px-4 py-2 text-foreground/80">Review guest-to-member applications</td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium">Reports</td>
              <td class="px-4 py-2 text-foreground/80">Review reported posts</td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium">Categories</td>
              <td class="px-4 py-2 text-foreground/80">Manage post/question categories</td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium">Invite Codes</td>
              <td class="px-4 py-2 text-foreground/80">Manage invite codes</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Dashboard -->
    <section id="admin-dashboard">
      <h2 class="text-xl font-bold text-foreground pb-2 border-b border-border mb-4">Dashboard</h2>
      <p class="text-sm text-foreground/80 mb-3">
        The dashboard provides an at-a-glance overview with stat cards:
      </p>
      <ul class="list-disc list-inside space-y-1 text-sm text-foreground/80">
        <li>Total Users, Posts, SIGs, Forms</li>
        <li>Pending Applications (requires attention)</li>
        <li>Pending Reports (requires attention)</li>
      </ul>
      <p class="text-sm text-foreground/80 mt-2">
        Quick navigation buttons jump directly to sub-sections. A recent applications preview list
        is also shown.
      </p>
    </section>

    <!-- User Management -->
    <section id="admin-user-management">
      <h2 class="text-xl font-bold text-foreground pb-2 border-b border-border mb-4">
        User Management
      </h2>

      <h3 class="text-lg font-semibold text-foreground mt-4 mb-3">Browsing Users</h3>
      <p class="text-sm text-foreground/80">
        Searchable, paginated table with username, display name, role badge, status (Active/Banned),
        join date, and actions.
      </p>

      <h3 class="text-lg font-semibold text-foreground mt-4 mb-3">Creating a User Account</h3>
      <ol class="list-decimal list-inside space-y-2 text-sm text-foreground/80">
        <li>Click <strong>Create Account</strong>.</li>
        <li>Fill in: username, password, display name, and role.</li>
        <li>Submit.</li>
      </ol>
      <BaseAlert type="warning" class="mt-3">
        <strong>Note:</strong> The account roles available for creation depend on your permission
        level.
      </BaseAlert>

      <h3 class="text-lg font-semibold text-foreground mt-4 mb-3">Bulk Operations</h3>
      <ol class="list-decimal list-inside space-y-2 text-sm text-foreground/80">
        <li>Select multiple users with checkboxes (or "Select All" on the current page).</li>
        <li>Click <strong>Bulk Change Role</strong>.</li>
        <li>Select the target role and confirm.</li>
      </ol>

      <h3 class="text-lg font-semibold text-foreground mt-4 mb-3">Per-User Actions</h3>
      <p class="text-sm text-foreground/80">
        As an Admin, you can browse and search all user accounts. However, per-user actions such as
        changing roles, banning, unbanning, and deleting users
        <strong>require Super Admin privileges</strong>.
      </p>
    </section>

    <!-- Applications -->
    <section id="admin-applications">
      <h2 class="text-xl font-bold text-foreground pb-2 border-b border-border mb-4">
        Membership Applications
      </h2>
      <ul class="list-disc list-inside space-y-2 text-sm text-foreground/80">
        <li><strong>Filter</strong> by status: Pending, Approved, Rejected.</li>
        <li>Each card shows: applicant's name, username, reason, date, status badge.</li>
        <li>
          For Pending applications: click <strong>Approve</strong> to grant membership or
          <strong>Reject</strong> to deny.
        </li>
      </ul>
    </section>

    <!-- Reports -->
    <section id="admin-reports">
      <h2 class="text-xl font-bold text-foreground pb-2 border-b border-border mb-4">
        Post Reports
      </h2>
      <ul class="list-disc list-inside space-y-2 text-sm text-foreground/80">
        <li><strong>Filter</strong> by status (Pending, Reviewed, Dismissed).</li>
        <li>Each report shows: reporter, reported post link, reason, date, status.</li>
        <li>
          Click <strong>Review</strong> to mark as Reviewed (take action) or Dismissed (no action
          needed).
        </li>
        <li>Navigate to the reported post to edit or delete it if needed.</li>
      </ul>
    </section>

    <!-- Categories -->
    <section id="admin-categories">
      <h2 class="text-xl font-bold text-foreground pb-2 border-b border-border mb-4">
        Category Management
      </h2>
      <ul class="list-disc list-inside space-y-2 text-sm text-foreground/80">
        <li><strong>Create:</strong> Click "Create Category", enter name and description.</li>
        <li><strong>Edit:</strong> Click Edit on a category, modify in the inline modal.</li>
        <li><strong>Delete:</strong> Click Delete and confirm.</li>
      </ul>
    </section>

    <!-- Invite Codes -->
    <section id="admin-invite-codes">
      <h2 class="text-xl font-bold text-foreground pb-2 border-b border-border mb-4">
        Invite Code Management
      </h2>
      <ul class="list-disc list-inside space-y-2 text-sm text-foreground/80">
        <li><strong>Filter</strong> by status: Active, Used, Revoked.</li>
        <li>Table shows: code, status, created date, used by, expiry.</li>
        <li><strong>Generate:</strong> Click "Generate Code" to create a new invite code.</li>
        <li>
          <strong>Copy:</strong> Click to copy a code to clipboard (visual feedback confirms).
        </li>
        <li><strong>Revoke:</strong> Invalidate a code so it can no longer be used.</li>
        <li><strong>Delete:</strong> Permanently remove the code record.</li>
      </ul>
    </section>

    <!-- Content Moderation -->
    <section id="admin-content-moderation">
      <h2 class="text-xl font-bold text-foreground pb-2 border-b border-border mb-4">
        Content Moderation
      </h2>
      <p class="text-sm text-foreground/80 mb-3">
        As an Admin, you have elevated permissions across all content:
      </p>

      <h3 class="text-lg font-semibold text-foreground mt-4 mb-3">Posts</h3>
      <ul class="list-disc list-inside space-y-1 text-sm text-foreground/80">
        <li><strong>Edit any post</strong> &mdash; not just your own.</li>
        <li><strong>Delete any post</strong> &mdash; with confirmation.</li>
        <li><strong>Pin / Unpin</strong> posts to the top of the forum.</li>
        <li><strong>Bulk delete</strong> multiple posts at once.</li>
        <li><strong>View edit history</strong> of any post.</li>
      </ul>

      <h3 class="text-lg font-semibold text-foreground mt-4 mb-3">Comments &amp; Files</h3>
      <ul class="list-disc list-inside space-y-1 text-sm text-foreground/80">
        <li><strong>Delete any comment</strong> (cannot edit other users' comments).</li>
        <li><strong>Delete any file</strong> and view file scan status for any file.</li>
      </ul>
    </section>

    <!-- Creating SIGs & Albums -->
    <section id="admin-create-sigs-albums">
      <h2 class="text-xl font-bold text-foreground pb-2 border-b border-border mb-4">
        Creating SIGs and Albums
      </h2>

      <h3 class="text-lg font-semibold text-foreground mt-4 mb-3">Creating a SIG</h3>
      <ol class="list-decimal list-inside space-y-2 text-sm text-foreground/80">
        <li>Navigate to SIGs and click <strong>Create SIG</strong>.</li>
        <li>Enter name and description.</li>
        <li>Submit. You become the SIG Admin by default.</li>
      </ol>

      <h3 class="text-lg font-semibold text-foreground mt-4 mb-3">Creating an Album</h3>
      <ol class="list-decimal list-inside space-y-2 text-sm text-foreground/80">
        <li>Navigate to Albums and click <strong>Create Album</strong>.</li>
        <li>Enter album name, description, and optional cover photo.</li>
        <li>Submit.</li>
      </ol>

      <p class="text-sm text-foreground/80 mt-3">
        You can also <strong>delete</strong> any SIG or album, and manage members/settings for any
        album.
      </p>
    </section>

    <!-- Cross-SIG & Cross-Form -->
    <section id="admin-cross-management">
      <h2 class="text-xl font-bold text-foreground pb-2 border-b border-border mb-4">
        Cross-SIG and Cross-Form Management
      </h2>
      <p class="text-sm text-foreground/80 mb-3">
        Platform Admins have elevated permissions across all SIGs:
      </p>
      <ul class="list-disc list-inside space-y-1 text-sm text-foreground/80">
        <li>Edit any SIG's name and description.</li>
        <li>Create forms within any SIG.</li>
        <li>Remove members, assign/demote Sub-Admins.</li>
        <li>Delete any SIG.</li>
      </ul>
      <p class="text-sm text-foreground/80 mt-3">
        Similarly, Admins can <strong>edit, view responses, export CSV, and delete</strong> any form
        on the platform.
      </p>
    </section>
  </div>
</template>
