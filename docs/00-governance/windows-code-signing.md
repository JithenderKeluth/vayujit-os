# Windows code-signing and public release

## Policy

VAYUJIT OS public Windows distribution requires an approved code-signing certificate or an approved
trusted signing service. Self-signed certificates, expired certificates, and test certificates do not
qualify. Signing materials must remain outside Git and outside the installer.

## Signing configuration

The repository keeps electron-builder signing external to application configuration. A release
workstation or CI secret manager may provide `CSC_LINK` and `CSC_KEY_PASSWORD` for the packaging
process, or the signing provider's approved certificate-store/service integration. Never place these
values in `.env` files, scripts, logs, or installer resources. Remove temporary signing environment
variables after packaging.

The signing provider must apply a trusted RFC 3161-compatible timestamp. A valid timestamp allows
normal Windows signature validation to survive certificate expiry according to the provider's policy.

## Verification

After `npm.cmd run package:windows`, verify both artifacts:

```powershell
Get-AuthenticodeSignature .\release\VAYUJIT-OS-0.1.0-rc.1-Setup.exe
Get-AuthenticodeSignature '.\release\win-unpacked\VAYUJIT OS.exe'
signtool verify /pa /v .\release\VAYUJIT-OS-0.1.0-rc.1-Setup.exe
```

Public release requires `Status = Valid`, the expected trusted publisher subject, a trusted chain,
and a valid timestamp for both the installer and packaged executable. `NotSigned`, `UnknownError`,
`HashMismatch`, and `NotTrusted` are release failures. Generate and independently verify the SHA-256
sidecar only after signing; signing changes the artifact bytes.

## Metadata and reputation

The installer metadata currently identifies `VAYUJIT OS`, version `0.1.0-rc.1`, and the local content
operations platform. The current unsigned packaged executable still reports Electron/GitHub metadata
because executable metadata editing is disabled in the established packaging configuration; this must
be corrected and re-verified as part of the signed release build. Do not invent a legal publisher name;
use the subject from the approved certificate.

A valid signature does not guarantee immediate Microsoft SmartScreen reputation. SmartScreen reputation
is established separately through publisher history, download telemetry, and Microsoft reputation systems.
Document any first-release warnings separately from signature validity.

## Current status

The internal/local Windows RC is GO. No approved public certificate, signing-service configuration, or
trusted timestamp is available in the current environment. The certificate store contains only
self-signed test certificates, so the public release remains NO-GO until signing evidence is supplied.