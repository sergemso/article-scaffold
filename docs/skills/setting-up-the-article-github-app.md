---
id: setting-up-the-article-github-app
title: Create the scaffold's GitHub App and install it on an article org
status: active
date: 2026-10-31
tags: [companion, github-app, procedural]
operationalizes: [app-key-stays-in-scaffold]
---

## Procedure

Owner steps. The app is created once under the personal account; steps 4 and 5's install part repeat for each further org or account.

1. In the personal account `sergemso`, Settings, Developer settings, GitHub Apps, New GitHub App. Name it, leave the webhook off, and under "Where can this app be installed" choose "Any account".
2. Repository permissions: Administration read and write, Contents read and write, Workflows read and write, Actions read, Metadata read. Nothing else.
3. Create the app, note the App ID, generate a private key (a `.pem` file).
4. Install the app on each article org or account (first `strebulaev-articles`; the installer must be an owner of that org) with "All repositories".
5. In `sergemso/article-scaffold`, Settings, Secrets and variables, Actions: add the secret `APP_PRIVATE_KEY` (the whole `.pem`), and the variables `APP_ID` (an app ID is not sensitive) and `APP_OWNERS` holding the allowed owners, one per line (`strebulaev-articles`; add each further owner here when you install the app there). Delete the `.pem` from disk.
6. Protect the scaffold's default branch (pull request required, no force push), because its workflows now hold a key that acts on every installed owner.
7. Run the bootstrap workflow with `dry_run` on and read the summary. Remove the old `GH_PAT` and `COMPANION_PAT` secrets only after a real bootstrap and publish succeed.

To rotate: generate a new key in the app settings, replace `APP_PRIVATE_KEY`, then revoke the old key.
