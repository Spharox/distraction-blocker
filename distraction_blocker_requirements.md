# Distraction Blocker — Requirements

## Purpose

A personal tool that blocks distraction sites by editing the system `hosts` file, with a deliberately annoying override mechanism. Willpower is not the primary defense — friction is.

## Scope

Small, single-purpose CLI or minimal GUI app. Target: working build in under an hour. No polish, no accounts, no cloud. Local-only.

## Core Functionality

### 1. Block List

- Maintain a local config file (`blocklist.json` or similar) containing:
  - List of domains to block (e.g., `x.com`, `reddit.com`, `youtube.com`)
  - For each domain: include common subdomains (`www.`, `m.`, `old.`, etc.)
- Domains are user-editable in the config file directly. No in-app management UI needed.

### 2. Blocking Mechanism

- Modify the system `hosts` file to redirect blocked domains to `127.0.0.1`.
- Requires admin/elevated privileges to run.
- On block: append entries with a clear marker (e.g., `# DISTRACTION_BLOCKER_START` / `# DISTRACTION_BLOCKER_END`) so entries can be cleanly removed later without touching other hosts entries.
- On unblock: remove only entries inside the marker block.
- Flush DNS after every hosts file change (`ipconfig /flushdns` on Windows, `sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder` on macOS, `sudo systemd-resolve --flush-caches` on Linux).

### 3. Modes

- **Block now for duration**: user specifies a duration (e.g., 2h, until 6pm). Block lifts automatically when the timer expires.
- **Scheduled block**: recurring windows (e.g., "block 9am–5pm every weekday"). Background process or scheduled task checks schedule.
- **Manual**: block/unblock on command.

### 4. Override (the important part)

To unblock early, the user must complete a deliberately annoying task. The override must be:

- **Interactive** — not a passive timer. Set-and-forget defeats the purpose.
- **Uninterruptible without restarting** — if you close the window or kill the process, you start over.
- **Boring enough that it's not worth doing for a 5-minute dopamine hit.**

Initial override: **click-the-dot task**
- A single dot appears on screen at a random position.
- Click it.
- Dot disappears, reappears at a new random position after a short delay (300–800ms).
- Must click N dots (start with 100) to unlock.
- Any misclick resets the counter to zero.
- Window must stay focused — if it loses focus, counter resets.

This is tunable. If 100 dots turns out to be too easy, increase. If it turns out to be punishing in a bad way, decrease. Goal is "annoying enough to lose the impulse," not "self-flagellation."

### 5. State Persistence

- Store current block state (active/inactive, end time, mode) in a local state file.
- On app start, reconcile state: if a scheduled block should be active but isn't, re-apply it.

## Technical Notes

- **Language**: Python is fine. Single script + config file is enough.
- **Admin elevation**: on Windows, use `ctypes.windll.shell32.IsUserAnAdmin()` to check, re-launch with `ShellExecuteW` runas verb if needed.
- **Hosts file path**:
  - Windows: `C:\Windows\System32\drivers\etc\hosts`
  - macOS/Linux: `/etc/hosts`
- **Override UI**: `tkinter` is sufficient for the dot-clicker. No need for anything heavier.
- **Scheduling**: simplest version is a background thread that checks the schedule every 30 seconds. Don't over-engineer with Task Scheduler/cron unless the simple version fails.

## Out of Scope (for v1)

- Browser extension integration
- Encrypted blocklists
- Usage analytics / time tracking
- Syncing across devices
- Blocking specific URLs or paths (domain-level only)
- Process/app blocking (only network-level via hosts)

## Success Criteria

- Can block a site and confirm it's unreachable in browser within 10 seconds of running the command.
- Can set a 2-hour block, walk away, and have it lift on its own.
- Override takes long enough that the impulse to unblock passes before the task is complete — at least once.

## Known Limitations (accept these)

- Hosts file blocking doesn't stop DNS-over-HTTPS in some browsers. If needed later, also block the DoH endpoints (`dns.google`, `cloudflare-dns.com`, etc.) or disable DoH in browser settings.
- Doesn't block the mobile phone. Separate problem, separate solution (delete apps).
- Doesn't block IP addresses directly — only domain lookups. Good enough for normal use.
