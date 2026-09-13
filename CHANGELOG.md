# Changelog

All notable changes to Distraction Blocker are documented here.

## 0.1.1 - 2026-09-13

### Fixed

- Stop and unregister the running worker before replacing its executable during an update
- Retry locked executable copies briefly and report a clear error when the GUI is still open

## 0.1.0 - 2026-09-09

### Added

- Timed and scheduled domain blocking on Windows
- Editable blocklist with common subdomain variants
- Focus-loss and misclick-reset early-unlock challenge
- Persistent background enforcement through Windows Task Scheduler
- Active-session blocklist snapshots that defer removals until a block ends
- Protected install layout separating privileged binaries and state from user configuration
- Legacy `SystemOptimizer` configuration migration
- Windows release packaging script and automated test workflow
