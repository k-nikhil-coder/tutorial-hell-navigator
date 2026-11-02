# Git Common Operations and Pitfalls

## Removing a Secret from History

If a secret was committed and pushed, deleting it in a new commit is **not** enough; the secret remains in older commits.

Recommended approach (using git-filter-repo):

```bash
# Install git-filter-repo first
git filter-repo --path .env --invert-paths
# or to replace the content
git filter-repo --path .env --path-rename .env:.env.removed
```

After rewriting history:

1. Force-push the cleaned branch: `git push --force-with-lease`
2. Every collaborator must re-clone or hard-reset to the new history.
3. Immediately rotate the leaked credentials.

`git rm --cached .env` only removes the file from the index of the current commit; history still contains it.

## Aborting a Rebase

When a rebase has conflicts and you want to return to the exact state before the rebase started:

```bash
git rebase --abort
```

If the repository is in a confused state and `--abort` fails:

```bash
git reflog
# find the commit hash that was HEAD before the rebase started
git reset --hard <pre-rebase-hash>
```

Never delete `.git/rebase-merge` manually unless you know exactly what you are doing.

## Local Configuration Files

Using `git update-index --skip-worktree` or `--assume-unchanged` on tracked config files is fragile; both flags are cleared by many rebase and checkout operations.

Preferred pattern:

1. Commit a template: `config.example.yaml` (or `.env.example`).
2. Add the real file to `.gitignore`: `config.yaml`, `.env`.
3. Provide a small bootstrap script that copies the example if the real file is missing.
4. Document that developers must create their own local copy.

This pattern survives rebase, merge, and clone cleanly.

## Merge vs Rebase on Shared Branches

- Use `git merge` when the branch is already public / shared with others. Merge creates a merge commit that preserves history.
- Use `git rebase` on private feature branches to keep a linear history before opening a pull request.
- Never rebase a branch that other people have already based work on, unless the whole team coordinates a force-push.

## Restoring a Single File from an Earlier Commit

```bash
git checkout <commit-hash> -- path/to/file
# or in modern Git
git restore --source=<commit-hash> path/to/file
```

This stages the restored content; commit it if you want the change recorded.
