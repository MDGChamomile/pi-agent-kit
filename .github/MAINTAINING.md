# Maintainer development and release history

Keep unmerged work on a task branch, not on local `updates`. The normal flow is:

```text
latest origin/updates -> local task branch -> remote task branch
-> PR into updates -> merge -> fetch and fast-forward local updates
```

The final fast-forward makes local `updates` match `origin/updates` without
creating another merge commit. GitHub merges do not update local branches
automatically.

Maintainers open `updates` -> `main` PRs only for explicitly authorized releases.
A release merge can leave a main-only merge commit even when no files differ;
this is an expected history difference, not missing development code. Identical
`main` and `updates` SHAs are not a development requirement.

With explicit authorization, maintainers can include that release history in
the next task branch and its PR instead of creating a separate history PR.
First verify that the main-only commits are completed `updates` -> `main`
release merges in this repository and that `origin/main` has the same file tree
as the merge-base of `origin/main` and `origin/updates`. Merge the verified main SHA into the task branch normally and
confirm its file tree is unchanged by that merge. Unexpected changes, conflicts,
or unverified history require separate review and authorization; matching trees
or commit messages alone do not establish provenance. Consider a separate
history-sync PR only when immediate synchronization is requested or combining it
with an authorized task is not appropriate.
