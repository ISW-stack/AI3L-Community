# AI3L Community — Contributor Onboarding Guide

> **Last Updated:** 2026-03-02
> **Audience:** All new contributors
> **Language:** English throughout

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Git: Concepts and First-Time Setup](#2-git-concepts-and-first-time-setup)
   - [How Git works](#21-how-git-works)
   - [Configure your identity](#22-configure-your-identity)
   - [Set your default editor](#23-set-your-default-editor)
   - [Authenticate with GitHub](#24-authenticate-with-github)
3. [Create a Local Folder and Clone the Repo](#3-create-a-local-folder-and-clone-the-repo)
4. [Set Up Environment Variables (.env)](#4-set-up-environment-variables-env)
5. [Start the Development Environment (Docker)](#5-start-the-development-environment-docker)
6. [Core Git Operations](#6-core-git-operations)
   - [Check Status](#61-check-status)
   - [Stage and Commit](#62-stage-and-commit)
   - [Push to Remote](#63-push-to-remote)
   - [Understanding Merge Conflicts](#64-understanding-merge-conflicts)
   - [Rebase](#65-rebase)
7. [Standard Collaboration Workflow (Feature Branch)](#7-standard-collaboration-workflow-feature-branch)
8. [Commit Message Convention](#8-commit-message-convention)
9. [Frequently Asked Questions](#9-frequently-asked-questions)

---

## 1. Prerequisites

Before you start, confirm the following tools are installed:

| Tool | Minimum Version | Install |
|------|----------------|---------|
| Git | 2.40+ | https://git-scm.com/downloads |
| Python | 3.11+ | https://python.org/downloads |
| Node.js | 20 LTS+ | https://nodejs.org |
| Docker Desktop | Latest | https://docs.docker.com/get-docker/ |
| VS Code | Latest | https://code.visualstudio.com (recommended editor) |

> **Windows users:** Use **Git Bash** or **WSL 2** for all commands. Native
> Command Prompt / PowerShell can cause path and line-ending issues.

Verify everything is installed correctly:

```bash
git --version
python --version
node --version
docker --version
docker compose version
```

---

## 2. Git: Concepts and First-Time Setup

### 2.1 How Git works

Git tracks changes across **four distinct locations**. Understanding this is the
key to understanding why `add`, `commit`, and `push` are three separate steps.

```
┌─────────────────────────────────────────────────────────────────┐
│  Your Computer                                                  │
│                                                                 │
│  ┌──────────────┐  git add   ┌──────────────┐  git commit      │
│  │   Working    │ ─────────► │   Staging    │ ──────────►      │
│  │  Directory   │            │    Area      │                  │
│  │  (your files)│ ◄───────── │ (snapshot    │  ┌────────────┐  │
│  └──────────────┘ git restore│  of changes) │  │   Local    │  │
│                              └──────────────┘  │    Repo    │  │
│                                                │ (.git/)    │  │
│                                                └─────┬──────┘  │
└──────────────────────────────────────────────────────┼─────────┘
                                                       │ git push
                                          ┌────────────▼──────────┐
                                          │   Remote Repo         │
                                          │   (GitHub)            │
                                          └───────────────────────┘
                                                       │ git pull / fetch
                                                       └──────────► back to Local
```

| Step | Command | What it does |
|------|---------|-------------|
| Edit files | (your editor) | Changes exist only in your Working Directory |
| Stage | `git add` | Marks specific changes to include in the next commit |
| Commit | `git commit` | Saves a permanent snapshot to your Local Repo |
| Push | `git push` | Uploads your local commits to GitHub |
| Pull | `git pull` | Downloads commits from GitHub to your Local Repo |

**Why not just one step?** Staging lets you commit only the changes that belong
together, even if you edited many unrelated files at once.

---

### 2.2 Configure your identity

Every commit you make is stamped with your name and email. Set this once,
globally, before your first commit:

```bash
git config --global user.name "Your Full Name"
git config --global user.email "your@email.com"
```

Use the same email address as your GitHub account. Verify the settings:

```bash
git config --global --list
```

---

### 2.3 Set your default editor

Several Git commands open an editor (interactive rebase, writing long commit
messages, resolving conflicts). The default is `vim`, which is very confusing
if you have never used it.

Set VS Code as your Git editor:

```bash
git config --global core.editor "code --wait"
```

Now whenever Git needs you to edit something, it opens a VS Code tab. Close
that tab when you are done, and Git continues.

> If you prefer a different editor, replace `"code --wait"` with:
> - nano: `"nano"`
> - Sublime Text: `"subl -n -w"`

---

### 2.4 Authenticate with GitHub

GitHub no longer accepts your account password for Git operations. You need
one of the following:

#### Option A — Personal Access Token (PAT) — easier for beginners

1. Go to **GitHub → Settings → Developer settings → Personal access tokens →
   Tokens (classic) → Generate new token (classic)**
2. Give it a name (e.g., `ai3l-dev`), set expiration, and tick the **`repo`**
   scope
3. Click **Generate token** and copy the token — you only see it once
4. The next time Git asks for your password (e.g., on first push), paste the
   token instead of your password

To avoid typing it every time, tell Git to remember it:

```bash
git config --global credential.helper store
```

After the first successful push, Git saves your credentials and stops asking.

> **Security note:** `credential.helper store` saves the token in plain text
> at `~/.git-credentials`. This is fine for a personal development machine.

#### Option B — SSH Key — more secure, recommended for long-term use

**Step 1: Generate a key pair**

```bash
ssh-keygen -t ed25519 -C "your@email.com"
# Press Enter to accept the default file location
# Set a passphrase (optional but recommended)
```

**Step 2: Copy the public key**

```bash
cat ~/.ssh/id_ed25519.pub
# Copy the entire output line
```

**Step 3: Add it to GitHub**

Go to **GitHub → Settings → SSH and GPG keys → New SSH key**, paste the
public key, and save.

**Step 4: Switch the repo remote to SSH**

```bash
git remote set-url origin git@github.com:Isaries/AI3L-Community.git
git remote -v   # verify the URL changed to git@github.com:...
```

**Step 5: Test the connection**

```bash
ssh -T git@github.com
# Expected: "Hi <username>! You've successfully authenticated..."
```

---

## 3. Create a Local Folder and Clone the Repo

### Step 1: Choose a working directory

```bash
# Example: create a projects folder in your home directory
mkdir -p ~/projects
cd ~/projects
```

> **Important:** Do NOT place the project inside OneDrive, iCloud, or Google
> Drive sync folders. These tools can corrupt Git state and cause issues with
> `node_modules`.

### Step 2: Clone the remote repo

```bash
git clone https://github.com/Isaries/AI3L-Community.git
cd AI3L-Community
```

After cloning, the directory structure looks like this:

```
AI3L-Community/
├── backend/           # FastAPI backend
├── frontend/          # Vue 3 + TypeScript frontend
├── nginx/             # Nginx configuration
├── scripts/           # Operational scripts
├── docker-compose.yml
├── .env               # ← you must create this yourself (not in repo)
└── ...
```

### Step 3: Verify the remote is set correctly

```bash
git remote -v
```

You should see:

```
origin  https://github.com/Isaries/AI3L-Community.git (fetch)
origin  https://github.com/Isaries/AI3L-Community.git (push)
```

---

## 4. Set Up Environment Variables (.env)

The `.env` file is excluded from the repo via `.gitignore`. Ask the project
lead for the values, or create a minimal dev version yourself.

Create `.env` in the `AI3L-Community/` root:

```bash
touch .env
```

Minimal working example:

```dotenv
# PostgreSQL
POSTGRES_USER=ai3l
POSTGRES_PASSWORD=changeme_dev
POSTGRES_DB=ai3l_community

# Redis
REDIS_PASSWORD=changeme_dev

# MinIO (object storage)
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=changeme_dev

# JWT
SECRET_KEY=dev-secret-key-replace-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# App
DEBUG=true
ALLOWED_ORIGINS=http://localhost:3000
```

> **Never commit `.env` or any real secret to the repo.**
> Production values must be obtained from the project lead separately.

---

## 5. Start the Development Environment (Docker)

This project uses Docker Compose to start all services together
(PostgreSQL, Redis, MinIO, FastAPI, Celery, Nginx).

```bash
# Run this from the AI3L-Community/ root
docker compose up --build
```

Once all services are healthy:

| Service | URL |
|---------|-----|
| Frontend (Nginx) | http://localhost:3000 |
| Backend API | http://localhost:3000/api/v1 |
| MinIO Console | http://localhost:9001 |

### Run the DB migration (first time only)

In a second terminal, while Docker is running:

```bash
docker compose exec fastapi alembic upgrade head
```

### Stop services

```bash
docker compose down        # stop, keep data volumes
docker compose down -v     # stop and delete all volumes (data reset)
```

### Run backend locally (without Docker)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows Git Bash: source .venv/Scripts/activate
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload
```

### Run frontend locally (without Docker)

```bash
cd frontend
npm install
npm run dev                 # dev server at http://localhost:5173
```

---

## 6. Core Git Operations

### 6.1 Check Status

```bash
git status
```

Reading the output:

```
On branch feature/my-task        ← your current branch

Changes to be committed:         ← staged (git add done), waiting to commit
  modified:   backend/app/...

Changes not staged for commit:   ← modified but not yet staged
  modified:   frontend/src/...

Untracked files:                 ← new files Git doesn't know about yet
  frontend/src/new-file.ts
```

Other useful inspection commands:

```bash
git diff                         # show unstaged changes
git diff --staged                # show staged changes waiting to commit
git log --oneline -10            # last 10 commits in one line each
```

---

### 6.2 Stage and Commit

**Staging** tells Git which changes to include in the next commit.

```bash
# Stage specific files (recommended — gives you precise control)
git add backend/app/services/post.py
git add frontend/src/views/PostView.vue

# Stage all changes (use carefully — review first to avoid staging .env etc.)
git add .

# Always double-check what you staged before committing
git status
git diff --staged
```

**Commit:**

```bash
git commit -m "feat: add post sorting by date"
```

> Do not add `Co-Authored-By:` lines to commit messages.

---

### 6.3 Push to Remote

```bash
# First push of a new branch — sets the upstream
git push -u origin feature/my-task

# All subsequent pushes on the same branch
git push
```

If the push is rejected because the remote has new commits:

```bash
git pull --rebase origin main    # rebase your commits on top of latest main
git push
```

---

### 6.4 Understanding Merge Conflicts

A **conflict** happens when two people edited the same lines of the same file.
Git cannot automatically decide which version to keep, so it pauses and asks
you to resolve it manually.

#### What a conflict looks like in a file

When you open a conflicting file, you will see markers like this:

```
<<<<<<< HEAD
    return format_post(row, include_author=True)
=======
    return format_post(row, include_author=False)
>>>>>>> a3f9c21 (fix: default author visibility to False)
```

| Marker | Meaning |
|--------|---------|
| `<<<<<<< HEAD` | Start of **your** version (the branch you are on) |
| `=======` | Dividing line between the two versions |
| `>>>>>>> <commit>` | End of the **incoming** version (from the other branch or rebase) |

#### How to resolve a conflict

1. **Open the file** in VS Code — it highlights conflicts with colored blocks
   and offers buttons: `Accept Current`, `Accept Incoming`, `Accept Both`
2. **Choose what to keep.** You can accept one side, the other, or write a
   completely new version that combines both ideas
3. **Delete all three marker lines** (`<<<<<<<`, `=======`, `>>>>>>>`) — they
   must not remain in the final file
4. **Stage the resolved file:**
   ```bash
   git add <filename>
   ```
5. **Continue** whatever operation triggered the conflict:
   ```bash
   git rebase --continue   # if you were rebasing
   git merge --continue    # if you were merging
   ```

#### Tip: use VS Code's built-in conflict UI

VS Code shows this toolbar above each conflict block:

```
Accept Current Change | Accept Incoming Change | Accept Both Changes | Compare Changes
```

Clicking one of these automatically removes the markers and applies the
selection, which is far easier than editing manually.

---

### 6.5 Rebase

Rebase moves your commits to sit on top of the latest `main`, keeping history
linear and clean.

**Scenario: you are on `feature/my-task` and `main` has received new commits**

```bash
# 1. Fetch the latest state from remote
git fetch origin

# 2. Rebase your feature branch on top of origin/main
git checkout feature/my-task
git rebase origin/main
```

If conflicts occur, follow the steps in [section 6.4](#64-understanding-merge-conflicts),
then run `git rebase --continue` until complete.

```bash
# To abandon the rebase entirely and restore the previous state
git rebase --abort
```

**Interactive rebase: clean up multiple commits before opening a PR**

```bash
# Rewrite the last 3 commits interactively
git rebase -i HEAD~3
```

VS Code opens a file listing your commits (because you set it as the editor
in section 2.3). Each line starts with a command word:

```
pick a1b2c3 feat: add post model
pick d4e5f6 fix: typo in post model
pick g7h8i9 fix: another typo
```

Change the command word to control what happens:

| Command | What it does |
|---------|-------------|
| `pick` | Keep the commit exactly as-is |
| `squash` (s) | Combine into the commit above it |
| `reword` (r) | Keep the commit but edit its message |
| `drop` (d) | Delete the commit entirely |

Example — squash the two typo fixes into the original commit:

```
pick a1b2c3 feat: add post model
squash d4e5f6 fix: typo in post model
squash g7h8i9 fix: another typo
```

Save and close the file. Git then opens another file for you to write the
combined commit message. Save and close that too, and the rebase is done.

---

## 7. Standard Collaboration Workflow (Feature Branch)

```
main ──────────────────────────────────────► (stable, never push directly)
        │
        └─ feature/your-task ─► open Pull Request ─► merged into main
```

### What is a Pull Request?

A **Pull Request (PR)** is a proposal on GitHub to merge your branch into
`main`. It gives the team a chance to review your changes, leave comments,
and ask for adjustments before the code becomes part of the main codebase.

You do not merge your own code — a reviewer approves it, then merges it.

### Full workflow step by step

```bash
# 1. Make sure your local main is up to date
git checkout main
git pull origin main

# 2. Create a new feature branch
git checkout -b feature/describe-your-task
# Examples: feature/add-comment-edit, fix/avatar-upload-error

# 3. Write code and tests
#    ... edit files ...

# 4. Run tests before committing
cd backend && pytest tests/ -v
cd frontend && npx vitest run

# 5. Stage and commit
git add <relevant files>
git commit -m "feat: add comment edit functionality"

# 6. Push to remote
git push -u origin feature/describe-your-task
```

### Opening a Pull Request on GitHub

After pushing your branch, go to the repository on GitHub:

**https://github.com/Isaries/AI3L-Community**

GitHub usually shows a yellow banner at the top:

```
─────────────────────────────────────────────────────────
  feature/describe-your-task had recent pushes
                                [Compare & pull request]
─────────────────────────────────────────────────────────
```

Click **"Compare & pull request"**. If the banner has disappeared, go to the
**Pull requests** tab → **New pull request** → select your branch manually.

On the PR creation page:

| Field | What to set |
|-------|-------------|
| **Base** | `main` (this is where your code will be merged into) |
| **Compare** | `feature/describe-your-task` (your branch) |
| **Title** | Short summary of what you did (e.g., `feat: add comment edit`) |
| **Description** | Explain *what* you changed and *why*; mention any related issue numbers |

Click **"Create pull request"** when ready.

```bash
# 7. Address review feedback — just push new commits to the same branch;
#    the PR updates automatically
git add <changed files>
git commit -m "fix: address review feedback on comment edit"
git push

# 8. After the PR is merged, clean up locally
git checkout main
git pull origin main
git branch -d feature/describe-your-task
```

### Branch naming rules

| Type | Format | Example |
|------|--------|---------|
| New feature | `feature/<short-desc>` | `feature/sig-join-api` |
| Bug fix | `fix/<short-desc>` | `fix/avatar-upload-error` |
| Refactor | `refactor/<short-desc>` | `refactor/post-repo-sql` |
| Documentation | `docs/<short-desc>` | `docs/update-onboarding` |

---

## 8. Commit Message Convention

This project follows [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>: <short description — English, imperative verb>
```

| Type | When to use |
|------|-------------|
| `feat` | Adding new functionality |
| `fix` | Fixing a bug |
| `refactor` | Restructuring code (no new feature, no bug fix) |
| `test` | Adding or updating tests |
| `docs` | Documentation changes |
| `style` | Formatting only (Prettier / Black, no logic change) |
| `chore` | Maintenance (dependency updates, config changes) |

Examples:

```bash
git commit -m "feat: add post sort by date parameter"
git commit -m "fix: avatar upload returns 500 on invalid mime type"
git commit -m "refactor: extract _row_to_comment converter"
git commit -m "test: add integration test for SIG join endpoint"
```

> Vague messages like `"update"`, `"fix bug"`, or `"WIP"` are not acceptable.

---

## 9. Frequently Asked Questions

### Q: `git push` fails with "rejected... non-fast-forward"

The remote has commits you don't have locally. Rebase first:

```bash
git pull --rebase origin main
# resolve any conflicts, then
git push
```

### Q: I accidentally committed `.env` or a secret file

```bash
# If NOT yet pushed:
git reset HEAD~1                  # undo the commit, keep changes in working dir
git restore --staged .env         # unstage .env
git commit -m "..."               # recommit without .env

# If already pushed: notify the project lead immediately and rotate all exposed keys.
```

### Q: How do I discard all local uncommitted changes

```bash
git restore .                     # restore all tracked files to last commit
git clean -fd                     # delete untracked files and folders (careful!)
```

### Q: How do I inspect what a specific commit changed

```bash
git show <commit-hash>
# Example
git show 1515190
```

### Q: My branch has diverged a lot from main and rebase has many conflicts

Work through them one commit at a time. Do not try to resolve everything at
once:

```bash
git rebase origin/main
# Resolve the conflict shown in the file, then:
git add <resolved-file>
git rebase --continue
# Repeat until Git says "Successfully rebased"
# At any point you can bail out with: git rebase --abort
```

### Q: Interactive rebase opened vim and I don't know how to exit

This happens when the editor was not set to VS Code. To exit vim without
saving: press `Esc`, then type `:q!` and press Enter.

Then set VS Code as your editor so this doesn't happen again:

```bash
git config --global core.editor "code --wait"
```

### Q: How do I run backend tests

```bash
cd backend
source .venv/bin/activate
pytest tests/ -v                              # all unit tests
INTEGRATION_TEST=1 pytest tests/ -v          # include integration tests (needs Docker running)
pytest tests/test_post.py -v                 # one specific test file
pytest tests/ -k "test_create_post" -v       # one specific test case
```

### Q: How do I run frontend tests

```bash
cd frontend
npx vitest run                # run all unit tests once
npx vitest run --watch        # watch mode — reruns on save
npm run lint                  # ESLint check
npm run build                 # verify TypeScript types compile cleanly
```

---

## Quick Reference Card

```bash
# === First time only ===
git config --global user.name "Your Name"
git config --global user.email "your@email.com"
git config --global core.editor "code --wait"
git config --global credential.helper store

# === Start of day ===
git checkout main && git pull origin main
git checkout feature/your-task

# === While working ===
git status                         # check current state
git diff                           # see unstaged changes
git add <file>                     # stage a specific file
git commit -m "type: description"  # commit

# === Before pushing ===
git fetch origin
git rebase origin/main             # make sure you're on top of latest main
git push

# === Inspection ===
git log --oneline -10              # last 10 commits
git show <hash>                    # what a commit changed
git diff origin/main               # difference from main
```

---

For questions, leave a comment on the relevant GitHub Issue or PR, or contact the project lead directly.
