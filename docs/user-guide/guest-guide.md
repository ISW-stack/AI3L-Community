# Guest User Guide

> **Role:** Guest — a temporary, read-only session obtained via an invite code.
>
> Guests can browse most content and submit forms, but cannot create posts, leave comments, send messages, or access social features. To unlock full functionality, [apply for membership](#applying-for-membership).

---

## Table of Contents

- [Getting Started](#getting-started)
- [Home Dashboard](#home-dashboard)
- [Browsing the Forum](#browsing-the-forum)
- [Browsing Q&A](#browsing-qa)
- [Special Interest Groups (SIGs)](#special-interest-groups-sigs)
- [Forms](#forms)
- [Albums](#albums)
- [Notifications](#notifications)
- [Profile](#profile)
- [Applying for Membership](#applying-for-membership)
- [Limitations](#limitations)

---

## Getting Started

### Guest Login

1. Navigate to the **Guest Login** page (`/guest`).
2. Enter a valid **invite code** provided by an existing member or admin.
3. Choose a **display name** for your temporary session.
4. Complete the **CAPTCHA** challenge (click the image to refresh if it is hard to read).
5. Click **Enter as Guest**.

Your session is temporary and stored server-side. If you are inactive for an extended period, your session will expire and you will need to log in again.

> **Tip:** If you want permanent access, consider [registering an account](#registering-instead) or [applying for membership](#applying-for-membership) from within your guest session.

### Registering Instead

If you have an invite code and want full Member access immediately:

1. Go to the **Register** page (`/register`).
2. Fill in: username, display name, invite code, password, and confirm password.
3. Password must meet all requirements: 8+ characters, uppercase, lowercase, digit, and special character. A live checklist shows your progress.
4. Complete the CAPTCHA and submit.

You will be logged in as a **Member** immediately.

---

## Home Dashboard

After logging in as a Guest, the home page shows:

- **Welcome card** with your display name and quick links to browse the forum and SIGs.
- **Guest alert banner** reminding you that your access is limited, with a link to register.
- **Membership application card** — shows your application status if you have submitted one, or a button to start the application process.
- **Recent posts** — the 5 newest posts across all SIGs.
- **Right sidebar:** community statistics (member/post/SIG counts), featured SIGs, and quick links.

---

## Browsing the Forum

Navigate to **Forum** from the navbar.

### What You Can See

- **Post feed** with titles, authors, category badges, comment counts, and timestamps.
- **Search** posts by keyword. Toggle "Advanced" for date range filters and AND/OR logic.
- **Sort** by Newest, Oldest, or Most Discussed.
- **Category filter** — click category pills (mobile) or sidebar items (desktop) to filter.
- **Post detail** — click any post to read the full content, view comments, co-authors, citations, and reactions.

### What You Cannot Do

- Create new posts
- Leave comments
- Add emoji reactions
- Report posts
- View post edit history

Posts load via infinite scroll — keep scrolling to load more.

---

## Browsing Q&A

Navigate to **Q&A** from the navbar.

- Browse questions sorted by Newest, Oldest, Most Answers, or Unanswered.
- Click a question to read the full detail and all answers.
- Questions with a best answer are marked with an "Answered" badge.

**Not available to guests:** asking questions, posting answers, voting on answers.

---

## Special Interest Groups (SIGs)

Navigate to **SIGs** from the navbar.

### SIG Directory

- Grid of SIG cards showing name, description, member count, and creation date.
- Use the search bar to filter by name or description.

### SIG Detail Page

Click a SIG to view its detail page with three tabs:

| Tab | What You Can See |
|---|---|
| **Posts** | All posts published within this SIG. Click to read full content. |
| **Members** | List of SIG members with their roles (Admin, Sub-Admin, Member). |
| **Forms** | Forms created for this SIG. You may be able to fill out and submit these. |

**Not available to guests:** joining/leaving SIGs, creating posts within a SIG.

---

## Forms

Navigate to **Forms** from the navbar, or access forms within a SIG.

### Browsing Forms

- The Forms Directory shows all standalone (non-SIG) forms.
- Each form card displays: title, status (active/closed), description, response count, deadline, and creator.
- Use the search bar to find forms by title.

### Submitting a Form

1. Click a form to open it.
2. A **progress bar** at the top tracks how many required questions you have answered.
3. Fill in each question:
   - **Text / Textarea** — type your response (character counter shown if there is a max length).
   - **Single Choice / Dropdown** — select one option.
   - **Multiple Choice** — check one or more options.
   - **Rating** — click a rating value on the scale.
   - **File Upload** — drag and drop or click to select a file.
4. Required questions are marked with an asterisk (*). The form validates on submit and highlights incomplete required fields.
5. Click **Submit**. After submission, you see a read-only summary of your answers.

> **Note:** Some SIG forms may restrict submissions to SIG members only. If you see an access error, you need Member status and SIG membership.

**Draft auto-save:** Your answers are saved locally as you type. If you leave and return, a "Draft restored" banner appears with the option to clear it.

---

## Albums

Navigate to **Albums** from the navbar.

- Browse the album grid showing cover photos, titles, member counts, and photo counts.
- Click an album to view its photos in a grid layout.
- Click a photo to open the **lightbox** (full-screen viewer with previous/next navigation).
- View album members and comments in the respective tabs.

**Not available to guests:** uploading photos, commenting on albums, joining albums.

---

## Notifications

Click the **bell icon** in the navbar to see your notification count, then navigate to the Notifications page.

- Filter by **All** or **Unread**.
- Click a notification to navigate to the related content (e.g., a post or comment).
- Mark notifications as read individually.

Notifications update in real time via WebSocket — you will see the count change without refreshing.

---

## Profile

Click your **avatar/name** in the navbar and select **Profile**.

As a Guest, your profile page is limited to:

- Viewing your display name and role badge (GUEST).
- Basic account information.

**Not available to guests:** editing profile details, changing password, generating invite codes, social features, deleting account.

---

## Applying for Membership

This is the most important action available to Guest users.

### From the Home Dashboard

1. On the home page, find the **Membership Application** card.
2. Click **Apply for Membership**.
3. In the modal, fill in:
   - **Username** — your desired permanent username.
   - **Password** — must meet the strength requirements (8+ chars, uppercase, lowercase, digit, special character).
   - **Display Name** — how others will see you.
   - **Reason** — explain why you want to join (up to 500 characters).
4. Submit the application.

### Application Status

After submitting, the card on your home page shows your application status:

| Status | Meaning |
|---|---|
| **Pending** | Your application is awaiting admin review. |
| **Approved** | Congratulations! Log out and log back in with your new credentials to access Member features. |
| **Rejected** | Your application was not approved. Contact an admin for more information. |

---

## Limitations

Here is a summary of what Guest users **cannot** do:

| Category | Restricted Actions |
|---|---|
| **Forum** | Create posts, comment, react, report, view edit history |
| **Q&A** | Ask questions, post answers, vote |
| **SIGs** | Join/leave SIGs, create posts in SIGs |
| **Forms** | Create or edit forms (submitting is allowed) |
| **Albums** | Upload photos, comment, join albums |
| **DMs** | Send or receive direct messages |
| **Social** | Friend requests, follow, block |
| **About** | Access the About section (intro, org chart, members directory) |
| **Profile** | Edit profile, change password, generate invite codes, delete account |
| **Admin** | Access any admin functionality |

To remove these limitations, [apply for membership](#applying-for-membership) or register a full account.
