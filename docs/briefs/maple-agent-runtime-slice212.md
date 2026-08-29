# Slice 212 brief - restricted host-owned HTTP transports

**Date:** 2026-08-29
**Class:** L (cross-cutting security boundary)
**Requested by:** MAPLE release-readiness objective

## Problem

The host-owned event, approval, human-input, and workflow transports validate
their configured endpoint schemes, but each call site used the standard
`urllib.request.urlopen()` opener. That leaves the allowed-scheme and
redirect policy implicit and makes Bandit's B310 audit depend on a call-site
exception rather than an owned boundary.

## Scope

- In: one private stdlib HTTP opener; HTTP(S)-only requests; rejection of URL
  credentials and malformed endpoints; same-origin redirect enforcement;
  HTTPS downgrade rejection; replacement of the five existing call sites;
  regression coverage; API/changelog/release evidence.
- Non-goals: public API changes, new dependencies, TLS termination or custom
  certificate policy, OAuth/mTLS, proxy policy changes, retries, persistence,
  hosted aggregation, or publication.

## Acceptance criteria

1. All five host-owned HTTP call sites use a transport that has no file,
   FTP, data, or custom-scheme handler.
2. A redirect cannot change origin, introduce URL credentials, or downgrade
   an HTTPS request; rejected redirects fail through the existing generic
   transport/error-isolation paths.
3. Existing bounded request/response, timeout, bearer-header, HTTP error, and
   typed `Result` behavior remains green across event, notification, and
   workflow transport tests.
4. The change adds no runtime dependency, preserves Python >=3.8 support,
   and passes Bandit without a new suppression.
5. Public transport documentation and the release evidence describe the
   redirect/security boundary accurately.

## Threat sketch

Assets: event payloads, approval and human-input notifications, bearer
tokens, and remote workflow request bodies. Entry points: configured URLs and
server-controlled redirects. Worst plausible abuse: a redirect sends a
credential-bearing or sensitive request to a file/custom handler or another
origin, or downgrades an HTTPS delivery.

## Constraints and assumptions

- The existing constructors remain the authoritative endpoint and HTTPS
  policy validators; the private opener is defense in depth at use time.
- Same-origin means matching normalized hostname and explicit port; a
  redirect with a different origin is rejected conservatively.
- Environment proxy support remains available through the stdlib
  `ProxyHandler`; no cookie or file/custom URL handlers are installed.

**Human confirmation:** the repository-local security hardening is within the
approved release-readiness objective; no external or legal-policy action is
included.
