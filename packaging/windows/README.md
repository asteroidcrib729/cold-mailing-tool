# Windows preview packaging

The GitHub **Windows preview installers** workflow produces a real per-user Inno
Setup EXE installer and a separately identified, unsigned MSIX preview. Neither
is a signed production release. It never publishes a GitHub release or uses signing
secrets. Start it with **Run workflow**, choose the branch, and leave `release_tag`
blank for a branch preview. An explicit tag must already exist as
`vMAJOR.MINOR.PATCH` and match the version inside that tag's `pyproject.toml`.

Source resolution freezes the full commit before dependency synchronization and
packaging. Tests, coverage gates, checksums, lock/source hashes, and installer
smoke evidence accompany artifacts. Do not create a tag just to fill an input.

The current account scope requires personal Google/Microsoft OAuth sign-in.
See the [publisher setup guide](../../development-plans/personal-account-setup.md).
An unsigned preview can open and rehearse offline without registrations. Real
browser sign-in still needs publisher client configuration; this workflow does
not create registrations, grant mailbox access, or supply user tokens. Before
distribution, validate configuration delivery and each provider's real callback,
refresh, revocation, and sending behavior in the packaged application.

For a local build from PowerShell:

```powershell
uv --cache-dir .uv-cache sync --locked --all-groups
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build_desktop.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install_inno.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/package_windows.ps1 -Format Both
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/smoke_installer.ps1
```

The compiler download is pinned to Inno Setup 6.7.3 and its upstream SHA-256.
The script also verifies its Windows signature and publisher before installation
into `reports/tools`. This compiler has its own commercial licensing terms; review
the [official licensing and downloads](https://jrsoftware.org/isdl.php) before
commercial distribution. The MSIX build requires Windows SDK **10.0.26100.0 x64**.
Generated package staging directories are unique and retained for inspection.

The EXE uses a stable preview AppId, installs below the current user's Programs
directory, adds a Start menu entry, and supports uninstall without deleting
external profile databases or OS credentials. The smoke script installs to an
isolated repository reports directory, launches against a synthetic profile,
reinstalls the same version, uninstalls, and verifies profile preservation. Run
the smoke once per fresh reports installation directory. Same-version reinstall
does not establish supported-version upgrade or rollback acceptance.

The MSIX identity is `ColdMailer.Preview`, publisher `CN=ColdMailerPreview`, with
numeric `MAJOR.MINOR.PATCH.0` versions. MakeAppx validates the manifest and package.
The unsigned artifact is for package inspection; ordinary installation requires
a matching trusted signing certificate or Store distribution. This workflow does
not install trust certificates or change machine sideload settings. Production
identity, certificate custody, signing, and install/upgrade/uninstall validation
remain separate gates. MSIX may virtualize application data; back up before
uninstall and verify actual retention on a clean test machine.

Use `dist/installers/SHA256SUMS.txt` to verify downloaded artifacts. A successful
local build does not establish a successful hosted workflow. Repository CI runs
cannot be dispatched until the uncommitted changes are reviewed and pushed.

References: [Inno privilege settings](https://jrsoftware.org/ishelp/topic_setup_privilegesrequired.htm),
[Inno verification](https://jrsoftware.org/isdl-verify.php),
[MakeAppx](https://learn.microsoft.com/en-us/windows/msix/package/create-app-package-with-makeappx-tool),
[MSIX signing](https://learn.microsoft.com/en-us/windows/msix/package/signing-package-overview).
