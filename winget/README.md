# WinGet manifests for ZhoelSherk.VALVET

Templates for the [Windows Package Manager community repo](https://github.com/microsoft/winget-pkgs). Inno Setup and NSIS are **not** used for v1: the asset is the PyInstaller **onedir zip**.

The last published package folder is **0.2.0** (ALPHA zip). This repo is **0.5.0 BETA**; do not invent a 0.5.0 installer URL until a matching GitHub Release zip exists.

## After a public GitHub Release

1. Run **Actions → Release Windows** (`workflow_dispatch`). First time leave **draft** on, download the artifact, launch `VALVET.exe` on a real PC.
2. Publish the Release (not draft). Asset name must stay `VALVET-<version>-windows-x64.zip`.
3. SHA256 of that zip (job log `sha256sum`, or `CertUtil -hashfile … SHA256`).
4. Put the hash in [`0.2.0/ZhoelSherk.VALVET.installer.yaml`](0.2.0/ZhoelSherk.VALVET.installer.yaml) (`InstallerSha256`, 64 hex chars). The all-zero value is a placeholder and must not be submitted.

Manifests use schema **1.12** (`ManifestVersion: 1.12.0`). Validate without admin:

```text
winget validate --manifest winget\0.2.0
```

### Local install test

Admin PowerShell first: `winget settings --enable LocalManifestFiles`. Then:

```text
winget install --manifest winget\0.2.0
```

`ArchiveBinariesDependOnPath: true` is required so Qt DLLs next to `VALVET.exe` resolve.

### First submission to winget-pkgs

Prefer **WingetCreate** (you already have `Microsoft.WingetCreate`) against the **public** asset URL:

```text
wingetcreate new https://github.com/zhoel-sherk/VALVET/releases/download/v0.2.0/VALVET-0.2.0-windows-x64.zip
```

When prompted:

- Nested exe path: `VALVET\VALVET.exe`
- *Does this executable depend on DLLs or any other files present in the zip archive?* → **Yes**
- PackageIdentifier: `ZhoelSherk.VALVET`
- Publisher: `Zhoel Sherk`
- License: `MIT`

Then `winget install --manifest <generated-folder>` before submitting the PR. GitHub token is required if WingetCreate opens the PR to `microsoft/winget-pkgs`.

Later versions:

```text
wingetcreate update ZhoelSherk.VALVET -u https://github.com/zhoel-sherk/VALVET/releases/download/vX.Y.Z/VALVET-X.Y.Z-windows-x64.zip -v X.Y.Z
```

## Signatures

WinGet trusts **InstallerSha256**, not Cosign/SmartScreen. Optional provenance from CI:

```text
gh attestation verify VALVET-0.2.0-windows-x64.zip --repo zhoel-sherk/VALVET
```
