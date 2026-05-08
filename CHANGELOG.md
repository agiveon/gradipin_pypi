# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.1.1] - 2026-05-08

### Changed
- The canonical public share URL is now read from the API response
  (`share_url` field on `POST /update-target`, `POST /heartbeat`, and
  `GET /apps/{app}/status`) instead of being constructed locally from a
  hard-coded template. This unblocks account-namespaced URLs like
  `/go/<account>/<app>` and lets the deployment change its public host
  without a client republish.
- `gradipin.share()` now prints the canonical public URL returned by the
  server. If the heartbeat ever sees a different `share_url` (e.g. the
  account moves to a custom domain mid-session), `_Session.public_url`
  is updated and a debug log line is emitted.
- `AppNotFoundError` and the `gradipin list` empty-state message now derive
  the dashboard URL from `GRADIPIN_API_URL` instead of hard-coding
  `https://gradipin.com/dashboard`.
- Default `GRADIPIN_API_URL` changed from `https://api.gradipin.com/v1` to
  `https://gradipin.lovable.app/api/v1` to match the current deployment.

### Added
- `_Session.public_url` attribute exposing the canonical public URL after
  `start()` has been called. Falls back to a derived URL
  (`{public_host}/go/{app}`) when the server doesn't supply one, so older
  API versions keep working.

### Backwards Compatibility
- Wire-protocol change is purely additive: clients keep working against
  servers that don't yet return `share_url`. They just print the
  derived-from-API-URL fallback instead of the canonical link.

## [0.1.0] - 2026-05-08

### Added
- Initial release. `gradipin.share()`, `gradipin.session()`, and
  `gradipin.status()` public API. `gradipin` CLI with `login`, `logout`,
  `list`, `status` subcommands. Background heartbeat thread, atexit-driven
  offline notification, and config resolution from
  args > env > `~/.gradipin/config` > `.env`.
