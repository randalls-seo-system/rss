# Git Hooks Setup

This repo uses shared git hooks at .githooks/. To activate them
in a fresh clone:

    git config core.hooksPath .githooks

This needs to run once per clone. The setting is local (stored in
.git/config) and doesn't travel with the repo.

The active hooks:

- `pre-commit`: Layer 2 enforcement. Rejects commits adding
  pipeline output files (manifests, article HTML drafts) or
  rendered article HTML in template directories. See CLAUDE.md
  for the broader enforcement strategy.

To bypass a specific hook for a single commit (not recommended):

    git commit --no-verify

For specific exception cases (e.g., committing a manifest fixture
for testing), set the environment variable:

    RSS_ALLOW_MANIFEST=1 git commit -m "your message"
