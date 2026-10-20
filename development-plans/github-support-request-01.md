# GitHub Support Request Draft: Residual Cached Sensitive History

Date: 2026-10-20 (Asia/Karachi).

Draft only. The agent has not submitted a support request or contacted other people.
The repository owner can submit this through [GitHub Support](https://support.github.com/).
GitHub may determine that credential revocation sufficiently mitigates the risk.

## Suggested request

Repository: `asteroidcrib729/cold-mailing-tool`.

The repository owner confirms exposed API keys and SMTP/app passwords have been
revoked or rotated. With explicit approval, we used git-filter-repo 2.47.0 sensitive-
data removal to purge legacy credential files, archives, databases, encryption
keys, a password image, and contact data from reachable repository history.

All eight branch heads were rewritten atomically with exact old-SHA leases and
unchanged current branch file contents. Seven open Dependabot PRs, #1 through #7,
were affected. All their advertised head/merge refs have regenerated. A fresh
full-ref remote clone scans with zero Gitleaks findings; no scanner allowlist was
added. No forks or release assets were present at inventory time. GitHub secret
scanning and push protection are enabled.

First changed original commit reported by git-filter-repo:
`6c1a33bf891611e7f1cc8bb463e8ada9e563cbdc`.

Rewritten application checkpoint:
`96f00148be40ce2f93118752c98fd9abe1adb1ad`.

No orphaned Git LFS objects were reported. Original local recovery history was
also purged after separate owner approval; local scans are clean.

A HEAD request after publication confirms the original commit URL is still
accessible. Please advise whether the residual cached exposure qualifies for
server-side garbage collection/cache invalidation and whether any historical PR
references need additional dereferencing. Please preserve the current cleaned
branches and current PR changes.

No secret values, private contact records, unredacted scanner output, or contaminated
repository bundle are included in this request. Credential revocation is owner-
confirmed, not independently tested against providers.
