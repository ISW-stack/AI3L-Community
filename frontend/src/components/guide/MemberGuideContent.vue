<script setup lang="ts">
import BaseAlert from '@/components/base/BaseAlert.vue'
</script>

<template>
  <div class="guide-content space-y-10">
    <BaseAlert type="info" class="mb-2">
      This guide covers features <strong>beyond</strong> what is available to Guests. Make sure you
      have read the <strong>Guest Guide</strong> tab first for browsing basics.
    </BaseAlert>

    <!-- Creating Posts -->
    <section id="member-creating-posts">
      <h2 class="text-xl font-bold text-foreground pb-2 border-b border-border mb-4">
        Creating and Managing Posts
      </h2>

      <h3 class="text-lg font-semibold text-foreground mt-4 mb-3">Creating a Post</h3>
      <ol class="list-decimal list-inside space-y-2 text-sm text-foreground/80">
        <li>
          Click the <strong>floating "+" button</strong> on the Forum page, or use Quick Links on
          the home dashboard.
        </li>
        <li>
          Fill in the post form:
          <ul class="list-disc list-inside ml-4 mt-2 space-y-1">
            <li><strong>Title</strong> (required)</li>
            <li><strong>Category</strong> &mdash; select from the dropdown.</li>
            <li><strong>SIG</strong> &mdash; optionally publish under a SIG you belong to.</li>
            <li>
              <strong>Content</strong> &mdash; rich-text editor with bold, italic, headings, lists,
              links, tables, code blocks, and more.
            </li>
            <li><strong>Keywords</strong> &mdash; up to 15 tags, each max 50 characters.</li>
            <li><strong>Allow Comments</strong> &mdash; checkbox (enabled by default).</li>
          </ul>
        </li>
        <li>Click <strong>Publish</strong>.</li>
      </ol>
      <BaseAlert type="info" class="mt-4">
        <strong>Auto-save drafts:</strong> Your post is automatically saved every second as you
        type. Drafts are per-SIG and per-user. If you leave and return, a banner offers to restore
        or discard the draft.
      </BaseAlert>

      <BaseAlert type="warning" class="mt-4">
        <strong>Navigation guard:</strong> If you try to leave with unsaved changes, a confirmation
        dialog appears.
      </BaseAlert>

      <h3 class="text-lg font-semibold text-foreground mt-6 mb-3">Editing a Post</h3>
      <p class="text-sm text-foreground/80">
        Open your post, click <strong>Edit</strong>, modify the content, and click
        <strong>Save</strong>. Each edit creates a new version. If someone else edits the post while
        you are editing, the system warns you of a <strong>version conflict</strong>.
      </p>

      <h3 class="text-lg font-semibold text-foreground mt-6 mb-3">Edit History, Delete & Report</h3>
      <ul class="list-disc list-inside space-y-2 text-sm text-foreground/80">
        <li>
          Click <strong>View Edit History</strong> on your own post to see all past versions with
          content differences.
        </li>
        <li>
          Click <strong>Delete</strong> on your own post and confirm in the modal. Deleted posts are
          soft-deleted and no longer visible.
        </li>
        <li>
          Click <strong>Report</strong> on any post that violates community guidelines. Enter a
          reason and submit for admin review.
        </li>
      </ul>

      <h3 class="text-lg font-semibold text-foreground mt-6 mb-3">Co-Authors</h3>
      <ul class="list-disc list-inside space-y-2 text-sm text-foreground/80">
        <li>
          On your post, open the <strong>Co-Author Manager</strong> to search and invite other
          members.
        </li>
        <li>
          You can also add <strong>external co-authors</strong> (people not on the platform) with a
          name and affiliation.
        </li>
        <li>
          Invitees see the invitation in <strong>Profile &gt; Social tab</strong> and can Accept or
          Decline.
        </li>
        <li>Accepted co-authors appear on the post with their avatars.</li>
      </ul>

      <h3 class="text-lg font-semibold text-foreground mt-6 mb-3">Citations</h3>
      <p class="text-sm text-foreground/80">
        In the post editor, use the <strong>citation search</strong> to find and link to other
        posts. On any post detail page, see "Cited by" and "References" sections.
      </p>
    </section>

    <!-- Q&A -->
    <section id="member-qa">
      <h2 class="text-xl font-bold text-foreground pb-2 border-b border-border mb-4">
        Q&A &mdash; Questions and Answers
      </h2>
      <ul class="list-disc list-inside space-y-2 text-sm text-foreground/80">
        <li>
          Click the <strong>"+" button</strong> on the Q&A page to ask a new question with title,
          content, category, and keywords.
        </li>
        <li>Open any question and scroll to the bottom to <strong>write an answer</strong>.</li>
        <li>
          Each answer has <strong>upvote / downvote</strong> buttons. Answers are sorted by vote
          score.
        </li>
        <li>
          If you are the question author, click the <strong>checkmark</strong> on the best answer to
          pin it to the top.
        </li>
      </ul>
    </section>

    <!-- Comments & Reactions -->
    <section id="member-comments-reactions">
      <h2 class="text-xl font-bold text-foreground pb-2 border-b border-border mb-4">
        Comments and Reactions
      </h2>
      <ul class="list-disc list-inside space-y-2 text-sm text-foreground/80">
        <li>
          On any post, scroll to the <strong>Comments</strong> section to write a comment or reply
          to an existing one.
        </li>
        <li><strong>Edit</strong> your own comments by clicking Edit, modifying, and saving.</li>
        <li><strong>Delete</strong> your own comments with a confirmation prompt.</li>
        <li>
          Posts and comments have an <strong>emoji reaction picker</strong>. Click to toggle
          reactions; counts and participants are shown.
        </li>
      </ul>
    </section>

    <!-- SIGs -->
    <section id="member-sigs">
      <h2 class="text-xl font-bold text-foreground pb-2 border-b border-border mb-4">
        Special Interest Groups (SIGs)
      </h2>

      <h3 class="text-lg font-semibold text-foreground mt-4 mb-3">Joining and Leaving</h3>
      <ul class="list-disc list-inside space-y-2 text-sm text-foreground/80">
        <li>
          Browse the SIG Directory and click <strong>Join</strong> on any SIG to become a member.
        </li>
        <li>
          Click <strong>Leave</strong> to exit a SIG. If you are the sole SIG Admin, transfer the
          role first.
        </li>
      </ul>

      <h3 class="text-lg font-semibold text-foreground mt-4 mb-3">Posting in a SIG</h3>
      <p class="text-sm text-foreground/80">
        On the SIG's Posts tab, click the <strong>"+" button</strong>. The post creation form opens
        with this SIG pre-selected.
      </p>

      <h3 class="text-lg font-semibold text-foreground mt-4 mb-3">Quick Comment &amp; Share</h3>
      <ul class="list-disc list-inside space-y-2 text-sm text-foreground/80">
        <li>
          On the SIG Posts tab, each post card has an <strong>expand button</strong> to preview
          comments and write a quick reply without navigating to the full post detail.
        </li>
        <li>
          Click <strong>Copy Share Link</strong> on the SIG header to copy the URL to your
          clipboard.
        </li>
      </ul>

      <h3 class="text-lg font-semibold text-foreground mt-4 mb-3">SIG Roles</h3>
      <div class="overflow-x-auto">
        <table class="w-full text-sm border border-border rounded-lg overflow-hidden">
          <thead class="bg-surface-alt">
            <tr>
              <th class="text-left px-4 py-2 font-medium text-foreground">SIG Role</th>
              <th class="text-left px-4 py-2 font-medium text-foreground">Permissions</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border">
            <tr>
              <td class="px-4 py-2 font-medium">Member</td>
              <td class="px-4 py-2 text-foreground/80">
                View content, post, comment within the SIG.
              </td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium">Sub-Admin</td>
              <td class="px-4 py-2 text-foreground/80">
                Member + create SIG forms, manage members within their authority.
              </td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium">Admin</td>
              <td class="px-4 py-2 text-foreground/80">
                Full SIG control: edit settings, assign/demote Sub-Admins, all Sub-Admin
                permissions.
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="text-sm text-muted mt-2">
        Platform administrators have elevated permissions across all SIGs.
      </p>
    </section>

    <!-- Forms -->
    <section id="member-forms">
      <h2 class="text-xl font-bold text-foreground pb-2 border-b border-border mb-4">
        Creating and Managing Forms
      </h2>

      <h3 class="text-lg font-semibold text-foreground mt-4 mb-3">Form Builder</h3>
      <p class="text-sm text-foreground/80 mb-3">
        Navigate to Forms and click <strong>Create Form</strong> (or create within a SIG). The form
        builder supports:
      </p>
      <ul class="list-disc list-inside space-y-2 text-sm text-foreground/80">
        <li>
          <strong>Metadata:</strong> Title, description (rich-text), banner image, deadline, max
          respondents, lock schema, allow non-members.
        </li>
        <li>
          <strong>Questions:</strong> Add, remove, duplicate, reorder (drag-and-drop with touch
          support), collapse/expand all.
        </li>
        <li><strong>Undo/Redo</strong> history for all changes.</li>
        <li><strong>Live preview</strong> in a side panel (desktop and mobile viewport modes).</li>
        <li><strong>Draft auto-save</strong> with restore/discard banner.</li>
      </ul>

      <h3 class="text-lg font-semibold text-foreground mt-4 mb-3">Question Types</h3>
      <div class="overflow-x-auto">
        <table class="w-full text-sm border border-border rounded-lg overflow-hidden">
          <thead class="bg-surface-alt">
            <tr>
              <th class="text-left px-4 py-2 font-medium text-foreground">Type</th>
              <th class="text-left px-4 py-2 font-medium text-foreground">Description</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border">
            <tr>
              <td class="px-4 py-2 font-medium">Text</td>
              <td class="px-4 py-2 text-foreground/80">
                Single-line input with optional max length
              </td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium">Textarea</td>
              <td class="px-4 py-2 text-foreground/80">
                Multi-line input with optional max length
              </td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium">Single Choice</td>
              <td class="px-4 py-2 text-foreground/80">Radio buttons &mdash; one selection</td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium">Multiple Choice</td>
              <td class="px-4 py-2 text-foreground/80">Checkboxes &mdash; multiple selections</td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium">Dropdown</td>
              <td class="px-4 py-2 text-foreground/80">Select menu &mdash; one selection</td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium">Rating</td>
              <td class="px-4 py-2 text-foreground/80">Numeric scale with min/max labels</td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium">File Upload</td>
              <td class="px-4 py-2 text-foreground/80">
                File attachment with type and size limits
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <h3 class="text-lg font-semibold text-foreground mt-6 mb-3">Viewing Responses & Export</h3>
      <ul class="list-disc list-inside space-y-2 text-sm text-foreground/80">
        <li>
          <strong>Individual tab:</strong> Browse each respondent's answers, filterable by search
          text and date range.
        </li>
        <li>
          <strong>Statistics tab:</strong> Bar charts for choice questions, averages for ratings,
          expandable text responses.
        </li>
        <li>
          <strong>Export CSV:</strong> Background task with progress modal; downloads automatically
          when complete.
        </li>
        <li><strong>Copy Share Link:</strong> Click to copy the form URL for easy distribution.</li>
      </ul>
    </section>

    <!-- Albums -->
    <section id="member-albums">
      <h2 class="text-xl font-bold text-foreground pb-2 border-b border-border mb-4">Albums</h2>
      <ul class="list-disc list-inside space-y-2 text-sm text-foreground/80">
        <li>
          <strong>Join</strong> an album from the album detail page. Some albums may require admin
          approval.
        </li>
        <li>
          <strong>Upload photos:</strong> On the Photos tab, click Upload. Drag-and-drop or select
          files (max 50 MB each, counts toward your 1 GB quota).
        </li>
        <li>
          Click any photo for the <strong>full-screen lightbox</strong> with keyboard navigation.
        </li>
        <li>Write and read <strong>album comments</strong> in the Comments tab.</li>
      </ul>
    </section>

    <!-- DM -->
    <section id="member-dm">
      <h2 class="text-xl font-bold text-foreground pb-2 border-b border-border mb-4">
        Direct Messages (DM)
      </h2>
      <p class="text-sm text-foreground/80 mb-3">
        Access via the <strong>envelope icon</strong> in the navbar, or click
        <strong>Send Message</strong> on a user's profile.
      </p>

      <h3 class="text-lg font-semibold text-foreground mt-4 mb-3">Conversation List</h3>
      <p class="text-sm text-foreground/80">
        The left panel shows all conversations with avatar, name, last message preview, timestamp,
        and unread badge. On mobile, list and thread toggle with a back button.
      </p>

      <h3 class="text-lg font-semibold text-foreground mt-4 mb-3">Sending Messages</h3>
      <ul class="list-disc list-inside space-y-2 text-sm text-foreground/80">
        <li>Type your message and press <strong>Enter</strong> or click the send button.</li>
        <li>
          <strong>File attachments:</strong> Click the attachment button to send a file (max 50 MB).
        </li>
      </ul>

      <h3 class="text-lg font-semibold text-foreground mt-4 mb-3">Edit & Recall</h3>
      <ul class="list-disc list-inside space-y-2 text-sm text-foreground/80">
        <li>
          Click <strong>"..."</strong> on your message to <strong>Edit</strong> or
          <strong>Recall</strong>.
        </li>
        <li>Both actions are available within a <strong>12-hour window</strong> after sending.</li>
        <li>Recalled messages show as "Message recalled" for both parties.</li>
      </ul>

      <h3 class="text-lg font-semibold text-foreground mt-4 mb-3">Read Receipts</h3>
      <p class="text-sm text-foreground/80">
        Single checkmark = sent. Double checkmarks = read by the recipient.
      </p>

      <h3 class="text-lg font-semibold text-foreground mt-4 mb-3">Privacy &amp; Retention</h3>
      <div class="overflow-x-auto">
        <table class="w-full text-sm border border-border rounded-lg overflow-hidden">
          <thead class="bg-surface-alt">
            <tr>
              <th class="text-left px-4 py-2 font-medium text-foreground">Setting</th>
              <th class="text-left px-4 py-2 font-medium text-foreground">Details</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border">
            <tr>
              <td class="px-4 py-2 font-medium">Friends Only</td>
              <td class="px-4 py-2 text-foreground/80">
                Toggle at top of Messages page. Only friends can message you when enabled.
              </td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium">Text retention</td>
              <td class="px-4 py-2 text-foreground/80">
                Auto-deleted after <strong>30 days</strong>.
              </td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium">File retention</td>
              <td class="px-4 py-2 text-foreground/80">
                Auto-deleted after <strong>3 days</strong>. Download important files promptly.
              </td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium">Conversation cap</td>
              <td class="px-4 py-2 text-foreground/80">
                50,000 characters per conversation. Oldest messages auto-deleted when cap is
                reached.
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="text-sm text-muted mt-2">
        You cannot message yourself, blocked users, or users with "Friends only" enabled unless you
        are friends.
      </p>
    </section>

    <!-- Social -->
    <section id="member-social">
      <h2 class="text-xl font-bold text-foreground pb-2 border-b border-border mb-4">
        Social Features
      </h2>

      <h3 class="text-lg font-semibold text-foreground mt-4 mb-3">Friends</h3>
      <ul class="list-disc list-inside space-y-2 text-sm text-foreground/80">
        <li>Visit a user's profile and click <strong>Add Friend</strong>.</li>
        <li>
          Manage requests in <strong>Friends &gt; Friend Requests</strong> tab (Accept / Decline).
        </li>
        <li>Unfriend from the Friends list with a confirmation modal.</li>
      </ul>

      <h3 class="text-lg font-semibold text-foreground mt-4 mb-3">Following</h3>
      <ul class="list-disc list-inside space-y-2 text-sm text-foreground/80">
        <li>
          Click <strong>Follow</strong> on a user's profile to add them to your Following list.
        </li>
        <li>
          <strong>Followers tab:</strong> See who follows you. Click <strong>Follow Back</strong> if
          desired.
        </li>
      </ul>

      <h3 class="text-lg font-semibold text-foreground mt-4 mb-3">Blocking</h3>
      <ul class="list-disc list-inside space-y-2 text-sm text-foreground/80">
        <li>
          Click <strong>Block</strong> on a user's profile. Blocked users cannot see your profile,
          message, or interact with you.
        </li>
        <li>
          Manage blocked users at <strong>Blocked Users</strong> page. Unblock with confirmation.
        </li>
      </ul>
    </section>

    <!-- About -->
    <section id="member-about">
      <h2 class="text-xl font-bold text-foreground pb-2 border-b border-border mb-4">About Page</h2>
      <p class="text-sm text-foreground/80 mb-3">
        Members have access to the About section (navbar dropdown):
      </p>
      <ul class="list-disc list-inside space-y-2 text-sm text-foreground/80">
        <li>
          <strong>Introduction:</strong> Platform overview with banner photo, description, and
          contributors grid.
        </li>
        <li>
          <strong>Org Chart:</strong> Hierarchical view by SIGs. SIG Admins/Sub-Admins can edit
          their SIG's description and their own bio.
        </li>
        <li>
          <strong>Members Directory:</strong> Searchable grid of all members (24 per page). Click a
          card to view the user's profile.
        </li>
      </ul>
    </section>

    <!-- Profile -->
    <section id="member-profile">
      <h2 class="text-xl font-bold text-foreground pb-2 border-b border-border mb-4">
        Profile Management
      </h2>
      <p class="text-sm text-foreground/80 mb-3">
        Click your avatar in the navbar and select Profile. The profile has 4 tabs:
      </p>

      <h3 class="text-lg font-semibold text-foreground mt-4 mb-3">General</h3>
      <ul class="list-disc list-inside space-y-1 text-sm text-foreground/80">
        <li>Upload avatar, edit display name, bio (rich-text), affiliation, ORCID.</li>
        <li>Storage usage bar showing used space vs. 1 GB quota.</li>
      </ul>

      <h3 class="text-lg font-semibold text-foreground mt-4 mb-3">Social</h3>
      <ul class="list-disc list-inside space-y-1 text-sm text-foreground/80">
        <li>Quick links to Friends, Following, Blocked Users.</li>
        <li>
          Co-Author Invitations: Accept or Decline pending invitations to collaborate on posts.
        </li>
      </ul>

      <h3 class="text-lg font-semibold text-foreground mt-4 mb-3">Security</h3>
      <ul class="list-disc list-inside space-y-1 text-sm text-foreground/80">
        <li>
          <strong>Change Password:</strong> Enter current password, new password, confirm. You will
          be logged out automatically after changing your password.
        </li>
        <li><strong>Generate Invite Code:</strong> Creates a shareable code. Copy to clipboard.</li>
      </ul>

      <h3 class="text-lg font-semibold text-foreground mt-4 mb-3">Danger Zone</h3>
      <ul class="list-disc list-inside space-y-1 text-sm text-foreground/80">
        <li>
          <strong>Delete Account:</strong> Permanent. Requires confirmation. Blocked if you are the
          sole admin of any SIG.
        </li>
      </ul>
    </section>

    <!-- File Uploads -->
    <section id="member-file-uploads">
      <h2 class="text-xl font-bold text-foreground pb-2 border-b border-border mb-4">
        File Uploads and Storage
      </h2>
      <div class="overflow-x-auto">
        <table class="w-full text-sm border border-border rounded-lg overflow-hidden">
          <thead class="bg-surface-alt">
            <tr>
              <th class="text-left px-4 py-2 font-medium text-foreground">Limit</th>
              <th class="text-left px-4 py-2 font-medium text-foreground">Value</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border">
            <tr>
              <td class="px-4 py-2 font-medium">Storage quota</td>
              <td class="px-4 py-2 text-foreground/80">
                1 GB per user (posts, albums, DMs, forms combined)
              </td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium">Max file size</td>
              <td class="px-4 py-2 text-foreground/80">50 MB per upload</td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium">Virus scanning</td>
              <td class="px-4 py-2 text-foreground/80">
                Uploaded files are automatically scanned for viruses. Downloads may be temporarily
                unavailable while scanning is in progress.
              </td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium">DM file retention</td>
              <td class="px-4 py-2 text-foreground/80">3 days (auto-deleted)</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="text-sm text-muted mt-2">Check your storage usage on Profile &gt; General tab.</p>
    </section>
  </div>
</template>
