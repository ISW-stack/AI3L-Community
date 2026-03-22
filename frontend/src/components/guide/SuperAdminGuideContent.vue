<script setup lang="ts">
import BaseAlert from '@/components/base/BaseAlert.vue'
</script>

<template>
  <div class="guide-content space-y-10">
    <!-- Additional Pages -->
    <section id="sa-additional-pages">
      <h2 class="text-xl font-bold text-foreground pb-2 border-b border-border mb-4">
        Additional Admin Panel Pages
      </h2>
      <p class="text-sm text-foreground/80 mb-3">
        The following pages are exclusively available to Super Admins in the Admin sidebar:
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
              <td class="px-4 py-2 font-medium">Audit Logs</td>
              <td class="px-4 py-2 text-foreground/80">Track all administrative actions</td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium">IP Bans</td>
              <td class="px-4 py-2 text-foreground/80">Block malicious IP addresses</td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium">Site Settings</td>
              <td class="px-4 py-2 text-foreground/80">Configure the About page content</td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium">Contributors</td>
              <td class="px-4 py-2 text-foreground/80">Manage the contributor list</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Audit Logs -->
    <section id="sa-audit-logs">
      <h2 class="text-xl font-bold text-foreground pb-2 border-b border-border mb-4">Audit Logs</h2>
      <p class="text-sm text-foreground/80 mb-3">
        Records all significant administrative actions on the platform.
      </p>
      <ul class="list-disc list-inside space-y-2 text-sm text-foreground/80">
        <li><strong>Filter</strong> by user ID, date from, and date to.</li>
        <li>Paginated table with: timestamp, user, action type, details.</li>
        <li>
          Logged events include: role changes, bans/unbans, deletions, application reviews, IP bans,
          invite codes, SIG operations.
        </li>
      </ul>
    </section>

    <!-- IP Bans -->
    <section id="sa-ip-bans">
      <h2 class="text-xl font-bold text-foreground pb-2 border-b border-border mb-4">
        IP Ban Management
      </h2>

      <h3 class="text-lg font-semibold text-foreground mt-4 mb-3">Creating an IP Ban</h3>
      <ol class="list-decimal list-inside space-y-2 text-sm text-foreground/80">
        <li>Click <strong>Add IP Ban</strong>.</li>
        <li>
          Enter <strong>IP Address</strong> (IPv4 or IPv6), <strong>Reason</strong>, and optional
          <strong>Expiry Date</strong>.
        </li>
        <li>Submit. Leave expiry blank for a permanent ban.</li>
      </ol>

      <h3 class="text-lg font-semibold text-foreground mt-4 mb-3">Removing an IP Ban</h3>
      <p class="text-sm text-foreground/80">
        Click <strong>Delete</strong> on the ban entry and confirm. The IP is immediately unblocked.
      </p>
    </section>

    <!-- Site Settings -->
    <section id="sa-site-settings">
      <h2 class="text-xl font-bold text-foreground pb-2 border-b border-border mb-4">
        Site Settings
      </h2>
      <p class="text-sm text-foreground/80 mb-3">
        Controls the content on the <strong>About &gt; Introduction</strong> page visible to all
        Members.
      </p>
      <ul class="list-disc list-inside space-y-2 text-sm text-foreground/80">
        <li>
          <strong>Introduction Photo:</strong> Click to upload a new image. Displayed on the About
          page immediately.
        </li>
        <li><strong>Introduction Text:</strong> Edit the bio/description text and save.</li>
      </ul>
      <p class="text-sm text-muted mt-2">
        Photo and text are saved independently &mdash; you can update one without affecting the
        other.
      </p>
    </section>

    <!-- Contributors -->
    <section id="sa-contributors">
      <h2 class="text-xl font-bold text-foreground pb-2 border-b border-border mb-4">
        Contributor Management
      </h2>
      <p class="text-sm text-foreground/80 mb-3">
        Manage the contributor cards displayed on the About page. Unlike the public view, this admin
        view shows GitHub usernames.
      </p>

      <h3 class="text-lg font-semibold text-foreground mt-4 mb-3">Adding a Contributor</h3>
      <ol class="list-decimal list-inside space-y-2 text-sm text-foreground/80">
        <li>Click <strong>Add Contributor</strong>.</li>
        <li>
          Fill in:
          <ul class="list-disc list-inside ml-4 mt-1 space-y-1">
            <li>
              <strong>GitHub Username</strong> &mdash; used to fetch avatar (proxied for privacy).
            </li>
            <li><strong>Display Name</strong> &mdash; public-facing name.</li>
            <li><strong>Role</strong> &mdash; title shown on the card.</li>
            <li><strong>Display Order</strong> &mdash; controls sort position.</li>
          </ul>
        </li>
        <li>Save.</li>
      </ol>
      <p class="text-sm text-foreground/80 mt-3">
        <strong>Edit</strong> or <strong>Delete</strong> contributors via the action buttons on each
        row.
      </p>
    </section>

    <!-- Role Management -->
    <section id="sa-role-management">
      <h2 class="text-xl font-bold text-foreground pb-2 border-b border-border mb-4">
        User Role Management
      </h2>

      <h3 class="text-lg font-semibold text-foreground mt-4 mb-3">Changing a Single User's Role</h3>
      <ol class="list-decimal list-inside space-y-2 text-sm text-foreground/80">
        <li>Go to <strong>Admin &gt; Users</strong>.</li>
        <li>Find the user and click <strong>Change Role</strong>.</li>
        <li>Select: Guest, Member, or Admin.</li>
        <li>Confirm. The change takes effect immediately.</li>
      </ol>

      <h3 class="text-lg font-semibold text-foreground mt-4 mb-3">Bulk Role Change</h3>
      <p class="text-sm text-foreground/80">
        Select multiple users with checkboxes, click <strong>Bulk Change Role</strong>, select the
        target role, and confirm.
      </p>

      <BaseAlert type="warning" class="mt-4">
        <strong>Restrictions:</strong> You cannot change your own role. Only Super Admins can
        promote users to Admin.
      </BaseAlert>
    </section>

    <!-- Ban & Deletion -->
    <section id="sa-ban-deletion">
      <h2 class="text-xl font-bold text-foreground pb-2 border-b border-border mb-4">
        User Ban and Deletion
      </h2>

      <h3 class="text-lg font-semibold text-foreground mt-4 mb-3">Banning a User</h3>
      <ul class="list-disc list-inside space-y-2 text-sm text-foreground/80">
        <li>Find the user in Admin &gt; Users and click <strong>Ban</strong>.</li>
        <li>The user is immediately logged out and cannot log back in.</li>
        <li>Their content remains on the platform.</li>
      </ul>

      <h3 class="text-lg font-semibold text-foreground mt-4 mb-3">Unbanning a User</h3>
      <p class="text-sm text-foreground/80">
        Click <strong>Unban</strong> on the user's row. They can log in again immediately.
      </p>

      <h3 class="text-lg font-semibold text-foreground mt-4 mb-3">Deleting a User Account</h3>
      <ul class="list-disc list-inside space-y-2 text-sm text-foreground/80">
        <li>Click <strong>Delete</strong> and confirm. Permanent removal.</li>
        <li>Cannot delete Super Admin accounts.</li>
        <li>Blocked if the user is the sole Admin of any SIG (role must be transferred first).</li>
      </ul>

      <BaseAlert type="warning" class="mt-4">
        <strong>Safety:</strong> You cannot ban yourself, delete Super Admin accounts, or change
        your own role.
      </BaseAlert>
    </section>

    <!-- Org Chart Overrides -->
    <section id="sa-org-chart">
      <h2 class="text-xl font-bold text-foreground pb-2 border-b border-border mb-4">
        Org Chart Overrides
      </h2>
      <ul class="list-disc list-inside space-y-2 text-sm text-foreground/80">
        <li>
          <strong>Visibility:</strong> Toggle SIGs or members visible/hidden. Hidden entries are
          only shown to Super Admins.
        </li>
        <li><strong>Display Order:</strong> Set custom sort values for SIGs and members.</li>
        <li>
          <strong>Edit:</strong> Modify any SIG's description or member's bio regardless of SIG
          membership.
        </li>
      </ul>
    </section>

    <!-- Health Monitoring -->
    <section id="sa-health">
      <h2 class="text-xl font-bold text-foreground pb-2 border-b border-border mb-4">
        System Health Monitoring
      </h2>
      <p class="text-sm text-foreground/80 mb-3">
        The <code>GET /health</code> endpoint (Super Admin only) returns comprehensive system
        health:
      </p>
      <ul class="list-disc list-inside space-y-1 text-sm text-foreground/80">
        <li>Database connection status and pool statistics (size, free, in-use).</li>
        <li>Redis connection status.</li>
        <li>MinIO (object storage) status.</li>
        <li>Celery worker status.</li>
        <li>Overall system health.</li>
      </ul>
      <p class="text-sm text-muted mt-2">
        The public <code>GET /health/live</code> endpoint returns only a basic liveness check.
      </p>
    </section>

    <!-- Capabilities Summary -->
    <section id="sa-capabilities">
      <h2 class="text-xl font-bold text-foreground pb-2 border-b border-border mb-4">
        Super Admin Exclusive Capabilities
      </h2>
      <div class="overflow-x-auto">
        <table class="w-full text-sm border border-border rounded-lg overflow-hidden">
          <thead class="bg-surface-alt">
            <tr>
              <th class="text-left px-4 py-2 font-medium text-foreground">Capability</th>
              <th class="text-left px-4 py-2 font-medium text-foreground">Details</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border">
            <tr>
              <td class="px-4 py-2 font-medium">Audit logs</td>
              <td class="px-4 py-2 text-foreground/80">Full history of administrative actions</td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium">IP bans</td>
              <td class="px-4 py-2 text-foreground/80">Create, view, and remove IP-based blocks</td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium">Site settings</td>
              <td class="px-4 py-2 text-foreground/80">Update About page photo and text</td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium">Contributors</td>
              <td class="px-4 py-2 text-foreground/80">Add, edit, remove contributor entries</td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium">Role changes</td>
              <td class="px-4 py-2 text-foreground/80">
                Promote/demote between Guest, Member, Admin
              </td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium">Ban / unban</td>
              <td class="px-4 py-2 text-foreground/80">Suspend and restore user accounts</td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium">Delete accounts</td>
              <td class="px-4 py-2 text-foreground/80">Permanently remove user accounts</td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium">Org chart overrides</td>
              <td class="px-4 py-2 text-foreground/80">Visibility and display order control</td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium">Health endpoint</td>
              <td class="px-4 py-2 text-foreground/80">Comprehensive system diagnostics</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>
