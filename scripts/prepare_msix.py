"""Prepare a separately identified unsigned preview package; never a Store identity."""

import argparse
import shutil
import tomllib

# Only the manifest generated below is parsed; external XML is never accepted.
import xml.etree.ElementTree as ET  # nosec B405
from pathlib import Path

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter, QPen

from scripts.release_metadata import windows_version


def prepare(root: Path, target: Path) -> None:
    payload = root / "dist/desktop/ColdMailer"
    if not (payload / "ColdMailer.exe").is_file():
        raise ValueError("Build the desktop payload first")
    if target.exists():
        raise ValueError("Choose a new package staging directory")
    shutil.copytree(payload, target)
    assets = target / "Assets"
    assets.mkdir()
    for name, size in (("Square44x44Logo", 44), ("Square150x150Logo", 150), ("StoreLogo", 50)):
        picture = QImage(size, size, QImage.Format.Format_ARGB32)
        picture.fill(QColor("#6452cf"))
        painter = QPainter(picture)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("white"), max(2, size / 30)))
        painter.drawRoundedRect(
            QRectF(size * 0.18, size * 0.27, size * 0.64, size * 0.46), size * 0.04, size * 0.04
        )
        painter.drawLine(int(size * 0.18), int(size * 0.28), int(size * 0.5), int(size * 0.52))
        painter.drawLine(int(size * 0.5), int(size * 0.52), int(size * 0.82), int(size * 0.28))
        painter.end()
        if not picture.save(str(assets / f"{name}.png")):
            raise OSError("Could not create package logo")
    version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "version"
    ]
    native = windows_version(version)
    manifest = f'''<?xml version="1.0" encoding="utf-8"?>
<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"
 xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10"
 xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities" IgnorableNamespaces="uap rescap">
 <Identity Name="ColdMailer.Preview" Publisher="CN=ColdMailerPreview" Version="{native}" ProcessorArchitecture="x64"/>
 <Properties><DisplayName>Cold Mailer Preview</DisplayName><PublisherDisplayName>Cold Mailer Project</PublisherDisplayName><Logo>Assets\\StoreLogo.png</Logo></Properties>
 <Resources><Resource Language="en-us"/></Resources>
 <Dependencies><TargetDeviceFamily Name="Windows.Desktop" MinVersion="10.0.19041.0" MaxVersionTested="10.0.26100.0"/></Dependencies>
 <Applications><Application Id="ColdMailer" Executable="ColdMailer.exe" EntryPoint="Windows.FullTrustApplication">
 <uap:VisualElements DisplayName="Cold Mailer Preview" Description="Local campaign authoring and review" BackgroundColor="#6452cf" Square150x150Logo="Assets\\Square150x150Logo.png" Square44x44Logo="Assets\\Square44x44Logo.png"/>
 </Application></Applications>
 <Capabilities><rescap:Capability Name="runFullTrust"/></Capabilities>
</Package>'''
    # The only substituted value has already passed numeric Windows version validation.
    ET.fromstring(manifest)  # nosec B314
    (target / "AppxManifest.xml").write_text(manifest, encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=Path, required=True)
    args = parser.parse_args()
    prepare(Path(__file__).resolve().parents[1], args.target)
