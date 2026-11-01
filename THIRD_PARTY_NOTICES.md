# Third-party licensing

Cold Mailer's original code and documentation are licensed under
[Apache-2.0](LICENSE). Dependencies, bundled runtimes, build tools, and provider
services retain their own licenses or service terms. This document is guidance,
not a complete inventory of every file in a frozen desktop build.

## Qt for Python

The desktop uses PySide6 Essentials, Shiboken6, and Qt. Their applicable commercial
or open-source licenses are separate from this application's Apache license.
Consult [Qt for Python licensing](https://doc.qt.io/qtforpython-6/licenses.html),
[Qt's LGPL obligations](https://www.qt.io/development/open-source-lgpl-obligations),
and the license files supplied with the exact wheels used for a build.

Before redistributing a frozen application, inventory the Qt modules and their
embedded third-party components, retain their notices and license texts, provide
the required corresponding source or a compliant source offer, and preserve the
ability to replace/relink the covered libraries. Assess installation and Store
restrictions for the intended distribution channel. The build uses a directory
payload with separate Qt libraries; that layout alone does not establish LGPL
compliance. Signing and third-party redistribution review remain release gates.

## Other components and tools

`pyproject.toml` declares dependencies and `uv.lock` pins resolved versions.
Review each distribution's installed metadata and license files, including
transitive dependencies. The Python runtime, SQLite, cryptography libraries,
PyInstaller bootloader, and components bundled by those tools also retain their
own terms. PyInstaller's bootloader exception does not relicense its dependencies.

The EXE compiler has separate [Inno Setup licensing terms](https://jrsoftware.org/isdl.php).
Windows SDK tooling is covered by Microsoft's terms. Installing a build tool does
not grant redistribution rights for every component it can package.

Google and Microsoft authorization and Google AI usage remain subject to their
respective provider terms and policies. The source-code license does not supply
provider credentials, grant mailbox access, or authorize contacting recipients.

## Distribution checks

- Include the application's `LICENSE` and readable `NOTICE` attribution.
- Preserve applicable dependency copyright and license notices.
- Produce a version-specific dependency/bundled-component inventory and include
  the required license texts, source materials/offers, and installation information.
- Review the exact EXE/MSIX contents and distribution channel before release.

The source/wheel checks and preview installer checks enforce inclusion of the
application's license and notices. They do not certify the complete third-party
redistribution obligations above.
