# Distraction Blocker

A small, offline Windows focus tool that blocks distracting websites and makes impulsive unblocking deliberately annoying.

Distraction Blocker edits the Windows hosts file through a protected background worker. Start a timed focus session, define recurring weekly schedules, and manage your own domain list from a minimal Tkinter interface. Ending a block early requires completing a 100-target click challenge that resets on a miss or loss of focus.

> [!IMPORTANT]
> This is a self-control aid, not security software, parental-control software, or an adversarial access-control system. A Windows administrator can always disable or remove it.

## Features

- Timed blocks from 30 minutes to a custom duration
- Recurring weekday schedules
- Editable domain blocklist with common subdomains included automatically
- Annoying but finite early-unlock challenge
- Active-session blocklist locking: removing a site cannot weaken a block already underway
- Local-only operation with no account, telemetry, subscription, or network service
- Background enforcement that restores the hosts entries if they drift

## Install

1. Download the latest `DistractionBlocker-vX.Y.Z-windows-x64.zip` from the GitHub Releases page.
2. Extract the archive.
3. Open PowerShell as Administrator in the extracted folder.
4. Run:

   ```powershell
   Set-ExecutionPolicy -Scope Process Bypass
   .\installer\install.ps1
   ```

The installer creates a desktop shortcut and a clearly named `DistractionBlockerWorker` scheduled task. Existing configuration from pre-release `SystemOptimizer` builds is migrated automatically.

### Updating

Close the Distraction Blocker window, extract the newer release, and run its installer again from an elevated PowerShell window:

```powershell
.\installer\install.ps1
```

The installer stops the existing background worker before replacing it and preserves your blocklist, schedule, and active state.

To remove the application, run `installer\uninstall.ps1` from an elevated PowerShell window.

## Build from source

Requirements:

- Windows 10 or 11
- Python 3.10 or newer
- PowerShell 5.1 or newer

```powershell
python -m pip install -r requirements.txt
.\build.ps1
.\package-release.ps1 -Version 0.1.0
```

Run the tests with:

```powershell
python -m unittest discover -s tests -v
```

## How blocking works

The worker runs as `SYSTEM` and maintains a marked section in the Windows hosts file. The GUI and editable configuration are kept separate from the worker executable and enforcement state. Standard users can change future blocklists and schedules but cannot replace the privileged worker binary.

When any timed or scheduled block begins, its domain list becomes monotonic until the underlying block ends. New domains can be added during the session; removing a domain only affects the next session. A temporary challenge-earned override does not discard this snapshot.

## Limitations and threat model

- Blocking is domain-wide; paths such as `example.com/feed` cannot be targeted separately.
- It does not block desktop applications, phones, virtual machines, VPN destinations, or direct IP access.
- Users with administrator access can stop the scheduled task, edit the hosts file, or uninstall the program.
- The local command/configuration files are intentionally user-editable. Someone determined to modify application data directly can bypass the intended UI friction.
- Unsigned community builds may trigger Microsoft SmartScreen warnings. Review the source and build locally if preferred.

Please report security-sensitive problems privately as described in [SECURITY.md](SECURITY.md).

Release history is recorded in [CHANGELOG.md](CHANGELOG.md).

## License

[MIT](LICENSE)
