<template>
  <div class="guide-content space-y-10">
    <!-- Getting Started -->
    <section id="guest-getting-started">
      <h2 class="text-xl font-bold text-foreground pb-2 border-b border-border mb-4">
        Getting Started
      </h2>

      <h3 class="text-lg font-semibold text-foreground mt-6 mb-3">Guest Login</h3>
      <ol class="list-decimal list-inside space-y-2 text-sm text-foreground/80">
        <li>Navigate to the <strong>Guest Login</strong> page (<code>/guest</code>).</li>
        <li>Enter a valid <strong>invite code</strong> provided by an existing member or admin.</li>
        <li>Choose a <strong>display name</strong> for your temporary session.</li>
        <li>
          Complete the <strong>CAPTCHA</strong> challenge (click the image to refresh if it is hard
          to read).
        </li>
        <li>Click <strong>Enter as Guest</strong>.</li>
      </ol>
      <p class="text-sm text-muted mt-3">
        Your session is temporary. If you are inactive for an extended period, your session will
        expire and you will need to log in again.
      </p>

      <h3 class="text-lg font-semibold text-foreground mt-6 mb-3">Registering Instead</h3>
      <p class="text-sm text-foreground/80 mb-2">
        If you have an invite code and want full Member access immediately:
      </p>
      <ol class="list-decimal list-inside space-y-2 text-sm text-foreground/80">
        <li>Go to the <strong>Register</strong> page (<code>/register</code>).</li>
        <li>Fill in: username, display name, invite code, password, and confirm password.</li>
        <li>
          Password must meet the strength requirements shown during registration. A live checklist
          shows your progress.
        </li>
        <li>Complete the CAPTCHA and submit.</li>
      </ol>
    </section>

    <!-- Home Dashboard -->
    <section id="guest-home-dashboard">
      <h2 class="text-xl font-bold text-foreground pb-2 border-b border-border mb-4">
        Home Dashboard
      </h2>
      <p class="text-sm text-foreground/80 mb-3">
        After logging in as a Guest, the home page shows:
      </p>
      <ul class="list-disc list-inside space-y-2 text-sm text-foreground/80">
        <li>
          <strong>Welcome card</strong> with your display name and quick links to browse the forum
          and SIGs.
        </li>
        <li>
          <strong>Guest alert banner</strong> reminding you that your access is limited, with a link
          to register.
        </li>
        <li>
          <strong>Membership application card</strong> &mdash; shows your application status or a
          button to start the application process.
        </li>
        <li><strong>Recent posts</strong> &mdash; the 5 newest posts across all SIGs.</li>
        <li>
          <strong>Right sidebar:</strong> community statistics (member/post/SIG counts), featured
          SIGs, and quick links.
        </li>
      </ul>
    </section>

    <!-- Browsing the Forum -->
    <section id="guest-browsing-forum">
      <h2 class="text-xl font-bold text-foreground pb-2 border-b border-border mb-4">
        Browsing the Forum
      </h2>
      <h3 class="text-lg font-semibold text-foreground mt-4 mb-3">What You Can See</h3>
      <ul class="list-disc list-inside space-y-2 text-sm text-foreground/80">
        <li>
          <strong>Post feed</strong> with titles, authors, category badges, comment counts, and
          timestamps.
        </li>
        <li>
          <strong>Search</strong> posts by keyword. Toggle "Advanced" for date range filters and
          AND/OR logic.
        </li>
        <li><strong>Sort</strong> by Newest, Oldest, or Most Discussed.</li>
        <li><strong>Category filter</strong> &mdash; click category pills or sidebar items.</li>
        <li>
          <strong>Post detail</strong> &mdash; click any post to read full content, view comments,
          co-authors, citations, and reactions.
        </li>
      </ul>
      <h3 class="text-lg font-semibold text-foreground mt-4 mb-3">What You Cannot Do</h3>
      <ul class="list-disc list-inside space-y-1 text-sm text-muted">
        <li>Create new posts</li>
        <li>Leave comments</li>
        <li>Add emoji reactions</li>
        <li>Report posts</li>
        <li>View post edit history</li>
      </ul>
    </section>

    <!-- Browsing Q&A -->
    <section id="guest-browsing-qa">
      <h2 class="text-xl font-bold text-foreground pb-2 border-b border-border mb-4">
        Browsing Q&A
      </h2>
      <ul class="list-disc list-inside space-y-2 text-sm text-foreground/80">
        <li>Browse questions sorted by Newest, Oldest, Most Answers, or Unanswered.</li>
        <li>Click a question to read the full detail and all answers.</li>
        <li>Questions with a best answer are marked with an "Answered" badge.</li>
      </ul>
      <p class="text-sm text-muted mt-2">
        Not available to guests: asking questions, posting answers, voting on answers.
      </p>
    </section>

    <!-- SIGs -->
    <section id="guest-sigs">
      <h2 class="text-xl font-bold text-foreground pb-2 border-b border-border mb-4">
        Special Interest Groups (SIGs)
      </h2>
      <p class="text-sm text-foreground/80 mb-3">
        Browse the SIG Directory to find groups. Click a SIG to view its detail page with three
        tabs:
      </p>
      <div class="overflow-x-auto">
        <table class="w-full text-sm border border-border rounded-lg overflow-hidden">
          <thead class="bg-surface-alt">
            <tr>
              <th class="text-left px-4 py-2 font-medium text-foreground">Tab</th>
              <th class="text-left px-4 py-2 font-medium text-foreground">What You Can See</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border">
            <tr>
              <td class="px-4 py-2 font-medium">Posts</td>
              <td class="px-4 py-2 text-foreground/80">All posts published within this SIG.</td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium">Members</td>
              <td class="px-4 py-2 text-foreground/80">
                List of SIG members with their roles (Admin, Sub-Admin, Member).
              </td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium">Forms</td>
              <td class="px-4 py-2 text-foreground/80">
                Forms created for this SIG. You may be able to submit these.
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="text-sm text-muted mt-2">
        Not available to guests: joining/leaving SIGs, creating posts.
      </p>
    </section>

    <!-- Forms -->
    <section id="guest-forms">
      <h2 class="text-xl font-bold text-foreground pb-2 border-b border-border mb-4">
        Submitting Forms
      </h2>
      <p class="text-sm text-foreground/80 mb-3">
        Guests can browse and submit forms. Open a form and fill in each question:
      </p>
      <ul class="list-disc list-inside space-y-2 text-sm text-foreground/80">
        <li><strong>Text / Textarea</strong> &mdash; type your response.</li>
        <li><strong>Single Choice / Dropdown</strong> &mdash; select one option.</li>
        <li><strong>Multiple Choice</strong> &mdash; check one or more options.</li>
        <li><strong>Rating</strong> &mdash; click a rating value on the scale.</li>
        <li><strong>File Upload</strong> &mdash; drag-and-drop or click to select a file.</li>
      </ul>
      <p class="text-sm text-foreground/80 mt-3">
        A <strong>progress bar</strong> at the top tracks how many required questions you have
        answered. Required questions are marked with an asterisk (*). Your answers are auto-saved
        locally as you type.
      </p>
      <p class="text-sm text-muted mt-2">
        Some SIG forms may restrict submissions to SIG members only.
      </p>
    </section>

    <!-- Albums -->
    <section id="guest-albums">
      <h2 class="text-xl font-bold text-foreground pb-2 border-b border-border mb-4">Albums</h2>
      <ul class="list-disc list-inside space-y-2 text-sm text-foreground/80">
        <li>Browse the album grid showing cover photos, titles, and photo counts.</li>
        <li>Click an album to view photos in a grid layout.</li>
        <li>Click a photo to open the full-screen lightbox with previous/next navigation.</li>
        <li>View album members and comments in the respective tabs.</li>
      </ul>
      <p class="text-sm text-muted mt-2">
        Not available to guests: uploading photos, commenting, joining albums.
      </p>
    </section>

    <!-- Notifications -->
    <section id="guest-notifications">
      <h2 class="text-xl font-bold text-foreground pb-2 border-b border-border mb-4">
        Notifications
      </h2>
      <ul class="list-disc list-inside space-y-2 text-sm text-foreground/80">
        <li>
          Click the <strong>bell icon</strong> in the navbar to see your notification count, then
          navigate to the Notifications page.
        </li>
        <li>Filter by <strong>All</strong> or <strong>Unread</strong>.</li>
        <li>Click a notification to navigate to the related content (e.g., a post or comment).</li>
        <li>Mark notifications as read individually.</li>
      </ul>
      <p class="text-sm text-muted mt-2">
        Notifications update in real time via WebSocket &mdash; you will see the count change
        without refreshing.
      </p>
    </section>

    <!-- Profile -->
    <section id="guest-profile">
      <h2 class="text-xl font-bold text-foreground pb-2 border-b border-border mb-4">Profile</h2>
      <p class="text-sm text-foreground/80 mb-3">
        Click your <strong>avatar/name</strong> in the navbar and select <strong>Profile</strong>.
      </p>
      <p class="text-sm text-foreground/80">As a Guest, your profile page is limited to:</p>
      <ul class="list-disc list-inside space-y-1 text-sm text-foreground/80 mt-2">
        <li>Viewing your display name and role badge (GUEST).</li>
        <li>Basic account information.</li>
      </ul>
      <p class="text-sm text-muted mt-2">
        Not available to guests: editing profile details, changing password, generating invite
        codes, social features, deleting account.
      </p>
    </section>

    <!-- Applying for Membership -->
    <section id="guest-apply-membership">
      <h2 class="text-xl font-bold text-foreground pb-2 border-b border-border mb-4">
        Applying for Membership
      </h2>
      <p class="text-sm text-foreground/80 mb-3">
        This is the most important action available to Guest users.
      </p>
      <ol class="list-decimal list-inside space-y-2 text-sm text-foreground/80">
        <li>On the home page, find the <strong>Membership Application</strong> card.</li>
        <li>Click <strong>Apply for Membership</strong>.</li>
        <li>
          Fill in: username, password (must meet strength requirements), display name, and reason
          (up to 500 characters).
        </li>
        <li>Submit the application.</li>
      </ol>

      <h3 class="text-lg font-semibold text-foreground mt-6 mb-3">Application Status</h3>
      <div class="overflow-x-auto">
        <table class="w-full text-sm border border-border rounded-lg overflow-hidden">
          <thead class="bg-surface-alt">
            <tr>
              <th class="text-left px-4 py-2 font-medium text-foreground">Status</th>
              <th class="text-left px-4 py-2 font-medium text-foreground">Meaning</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border">
            <tr>
              <td class="px-4 py-2 font-medium">Pending</td>
              <td class="px-4 py-2 text-foreground/80">Awaiting admin review.</td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium">Approved</td>
              <td class="px-4 py-2 text-foreground/80">
                Log out and log back in with your new credentials.
              </td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium">Rejected</td>
              <td class="px-4 py-2 text-foreground/80">Contact an admin for more information.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Limitations -->
    <section id="guest-limitations">
      <h2 class="text-xl font-bold text-foreground pb-2 border-b border-border mb-4">
        Guest Limitations
      </h2>
      <div class="overflow-x-auto">
        <table class="w-full text-sm border border-border rounded-lg overflow-hidden">
          <thead class="bg-surface-alt">
            <tr>
              <th class="text-left px-4 py-2 font-medium text-foreground">Category</th>
              <th class="text-left px-4 py-2 font-medium text-foreground">Restricted Actions</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border">
            <tr>
              <td class="px-4 py-2 font-medium">Forum</td>
              <td class="px-4 py-2 text-foreground/80">
                Create posts, comment, react, report, view edit history
              </td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium">Q&A</td>
              <td class="px-4 py-2 text-foreground/80">Ask questions, post answers, vote</td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium">SIGs</td>
              <td class="px-4 py-2 text-foreground/80">Join/leave SIGs, create posts in SIGs</td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium">Forms</td>
              <td class="px-4 py-2 text-foreground/80">
                Create or edit forms (submitting is allowed)
              </td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium">DMs / Social</td>
              <td class="px-4 py-2 text-foreground/80">Messages, friend requests, follow, block</td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium">About</td>
              <td class="px-4 py-2 text-foreground/80">
                Entire About section (intro, org chart, members)
              </td>
            </tr>
            <tr>
              <td class="px-4 py-2 font-medium">Profile</td>
              <td class="px-4 py-2 text-foreground/80">
                Edit profile, change password, generate invite codes, delete account
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="text-sm text-muted mt-3">
        To remove these limitations, apply for membership or register a full account.
      </p>
    </section>
  </div>
</template>
