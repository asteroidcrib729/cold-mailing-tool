# Historical Secret Remediation 01

Date: 2026-10-20 (Asia/Karachi).

The owner requested historical remediation before live testing and confirmed that
exposed Gemini API keys and SMTP/app passwords have been revoked or rotated.
That is owner confirmation, not a provider-validity test. No exposed credential is
printed, reused, submitted to a validity endpoint, or included in this document.

## Audit and scope

The original full local Git scan reported six findings across credential-bearing
legacy paths. Historical archives, databases, encryption keys, a password image,
and contact data also require path removal: a text scanner alone cannot establish
their safety. Before remediation the working tip already excluded these files,
but their old blobs were reachable through ancestry. The advertised branch/PR ref
histories and this checkout are now clean by the checks recorded below.

The verified GitHub destination is `asteroidcrib729/cold-mailing-tool`, a public
repository owned by the authenticated account, with administrative/push access.
At preparation time it has eight branch heads, no tags, no forks, seven open
Dependabot PRs, no releases, and 13 synthetic test-result artifacts. Those artifacts
are not classified as credential-bearing merely because they exist. Secret scanning
and push protection were disabled; both have now been enabled and read back from
the API response. Credential-validity checks remain disabled.

## Prepared isolated rewrite

A fresh full-ref mirror lives under ignored
`reports/secret-remediation/sanitized.git`. The dedicated tool environment pins
the maintained `git-filter-repo` release **2.47.0**, without changing application
dependencies. No contaminated backup bundle was created; the existing working
repository remains untouched during preparation.

The rewrite removes these paths throughout all fetched history:

```text
!APP_VERSIONS/
b2b_cold_email_tool_v2/
b2b_cold_email_tool_v3/
b2b_cold_email_tool_v4/
.env
config.db
secret.key
Load Contacts.csv
Google-GenerativeAI-List-Models.py
List_Models.py
```

The tool runs with `--sensitive-data-removal --invert-paths`; `--no-fetch` is used
only because the just-created mirror already contains all 22 advertised branch/PR
refs. A later publication preflight must check current remote branch names and
SHAs again. Changed/new remote branches must abort publication and trigger a fresh
inventory, not be silently discarded.

Verification of the prepared mirror:

- Gitleaks full-history scan: **zero findings**, with no allowlist or exclusions
  added. At preparation time the original working repository still reported six
  findings; its later reconciliation is verified below.
- Every one of the **22 ref-tip Git tree IDs is unchanged**. This proves exact
  current file content preservation for main, dependency branches, and fetched PR
  head/merge refs. It does not claim historical file contents remain unchanged.
- Removed-path reachability: **zero remaining paths** in reachable Git objects.
- `git fsck --full --no-reflogs --unreachable`: passes with no unreachable objects
  reported in the sanitized mirror.
- Prepared main changes from `526ca6f97378ef26fb98199869550a7d2216cdac` to
  `96f00148be40ce2f93118752c98fd9abe1adb1ad`.

Redacted scan reports, before/after ref maps, tool fingerprint, and filter-repo
commit/ref maps are retained locally under `reports/secret-remediation/`. These
are evidence files, not an instruction to publish the reports directory.

## Publication and local checkout procedure

The concrete publication scope is `main` and all seven inventoried Dependabot
branches. Use one **atomic push with an exact old-SHA lease per branch**, and
explicit new-SHA-to-head refspecs. Never use an unrestricted mirror push, silently
delete branches, disable protection, or override a failed lease. No tags exist.
Commit IDs change; current branch file trees remain identical.

GitHub's `refs/pull/*` namespace is read-only. The mirror's sanitized PR refs cannot
be pushed directly. Updating branch heads may refresh PR refs, but is not proof
that old PR versions/cached commits have been removed. Seven PRs are affected;
their dependency changes must not be merged merely to simplify cleanup.

After successful publication:

1. Query the actual GitHub branch heads and compare every one to the sanitized
   ref map; verify the complete branch-name set.
2. Fresh-clone and scan the published branch history; separately inspect PR refs
   so a branch-only success cannot be mistaken for server-wide erasure.
3. Reconcile this local checkout and other clones. Do not merge the old history
   into the cleaned history. A new clone is preferred; preserve local-only data
   separately before changing any existing clone.
4. Inventory local backup/Codex refs and reflogs. The original working repository
   has local-only refs that are outside GitHub; neither a remote rewrite nor a
   clean mirror removes those automatically. Do not claim the original `.git`
   directory is clean until those references and unreachable objects are addressed.
5. Request GitHub Support assistance for any residual cached/PR references when
   appropriate. Do not send raw credentials, unredacted scans, or contaminated
   repositories. Support eligibility is decided by GitHub.
6. Run the full-history security workflow on the published cleaned history and
   record the hosted result. Keep the full-history scanner enabled.

## Remaining boundaries

The prepared rewrite has now been published and freshly verified. Rotation is confirmed by the owner;
Git object removal cannot revoke credentials. Other people's clones, unknown
external copies, GitHub caches, and old artifacts cannot be declared erased by a
local scan. Existing clones need coordinated cleanup or re-cloning to prevent
reintroduction. Release artifacts built before the rewrite retain their historical
source metadata and must be rebuilt before release acceptance.

Status: approved remote rewrite and local cleanup completed; reachable-history
scans pass. GitHub's old cached commit URL remains accessible and needs external
support follow-up. The owner has confirmed submitting the support ticket.
Application [live testing has started](live-testing-01.md); successful AI generation
and SMTP seed acceptance remain open.

## Approval review result

Automatic approval review rejected the proposed atomic publication before the
publish script ran. Its stated reason was that historical-remediation authorization
did not explicitly approve force-rewriting these eight remote branches and their
irreversible collaboration/PR-history effects. No alternate execution mechanism
or unguarded push was attempted.

The owner then explicitly approved publication to **main and all seven Dependabot
branches**. That atomic leased push completed and all eight heads were verified.
No branch or tag was deleted.

A separate automatic review initially rejected permanent local reflog/object
cleanup as outside that remote approval. The owner explicitly approved local
cleanup in response. Ref reconciliation and permanent cleanup then completed with
file/index preservation checks. Neither rejection was bypassed.

## Completed verification

- The exact approved eight-branch update completed atomically; every old-SHA lease
  matched. Application checkpoint `96f00148be40ce2f93118752c98fd9abe1adb1ad`
  preserves the old application tree. Subsequent documentation commits intentionally
  update the incident record without changing application behavior.
- All seven open PRs now use the rewritten heads and main base. A fresh full mirror
  from GitHub includes all 22 advertised heads/PR refs, including regenerated merge
  refs. Gitleaks scans that history with **zero findings**.
- The local checkout's main and remote-tracking refs were reconciled with compare-
  and-swap checks. The two local Codex refs are standalone clean content trees,
  not history-bearing commits; they were audited and preserved unchanged.
- Hash comparisons preserve 117 working/private files and the Git index during
  reconciliation/purge. The four private root files match the original protected
  baseline; none was opened as an application fixture or deleted.
- With explicit owner approval, old reflogs, ORIG_HEAD/FETCH_HEAD recovery metadata,
  and obsolete Git objects were purged. Git integrity checks pass, report zero
  unreachable objects, and cannot find the original exposed commit locally.
  A fresh full local history scan also has **zero findings**.
- GitHub secret scanning and push protection remain enabled. Alert 1 is recorded
  as `resolved/revoked` based on owner confirmation; provider validity remains
  `unknown`. No provider-validity requests or scanner suppressions were introduced.
- Hosted [Development checks](https://github.com/asteroidcrib729/cold-mailing-tool/actions/runs/39429828716),
  [Security checks](https://github.com/asteroidcrib729/cold-mailing-tool/actions/runs/39429828743),
  and [CodeQL](https://github.com/asteroidcrib729/cold-mailing-tool/actions/runs/39429828714)
  all pass for the rewritten application checkpoint. This does not establish hosted
  EXE/MSIX acceptance or live-provider behavior.
- A body-free HEAD request confirms GitHub still serves the original exposed
  commit URL. No raw historical source or credential was retrieved for that check.
  Reachable-ref cleanup therefore does not establish complete server-side erasure.

The [GitHub Support request record](github-support-request-01.md) retains the
remaining cache/garbage-collection request. The owner confirmed submission on
2026-10-20; no support reply or completed cache removal has been verified. GitHub
decides whether revoked credentials warrant further server-side cleanup; external
clones and previously copied artifacts remain outside this repository's control.

References: [GitHub's sensitive-data removal procedure](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository),
[git-filter-repo manual](https://github.com/newren/git-filter-repo/blob/main/Documentation/git-filter-repo.txt),
and [repository security API](https://docs.github.com/en/rest/repos/repos#update-a-repository).
