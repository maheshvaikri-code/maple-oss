# ADR-086: Bounded multimodal image content

Status: Accepted for preview

Date: 2026-08-27

## Context

MAPLE's LLM boundary previously accepted text-only `ChatMessage` content. The
top comparison runtimes expose multimodal message inputs, but unrestricted
media bytes, implicit URL fetching, provider-specific payloads, and durable
replay would widen the security and reliability boundary before the host has
chosen a media service.

## Decision

Add the typed `ImageContent` part and allow a `ChatMessage` to contain either
text or a bounded ordered list of text and image parts. An image source must
be an HTTPS URL or a validated base64 data URI for JPEG, PNG, WebP, or GIF. The
part count and UTF-8 source/content sizes are bounded, image detail is limited
to `auto`, `low`, or `high`, and credentials in URL userinfo are rejected.

The OpenAI-compatible adapter emits text and `image_url` items for both
supported source forms. The Anthropic adapter emits base64 image source items
and returns a typed unsupported-content error for HTTPS URLs. Neither adapter
fetches media through MAPLE. `ProviderCapabilities.image_input` and
`ProviderRequirements.image_input` allow hosts to make capability selection
explicit.

Session messages and durable run checkpoints serialize image parts as bounded
JSON-safe objects and restore them without executing or resolving their
sources. Existing string messages and tool-result messages remain compatible.

## Alternatives considered

| Alternative | Decision |
| --- | --- |
| Accept arbitrary provider payload dictionaries | Rejected: it bypasses size, scheme, and serialization bounds. |
| Fetch remote images inside MAPLE | Rejected: it introduces SSRF, network policy, caching, and credential exposure concerns. |
| Convert every image to bytes in MAPLE | Rejected: media storage and transcoding are host-owned concerns. |
| Add audio/video in the same contract | Deferred: provider support, quotas, codecs, and persistence rules differ materially. |

## Security and failure boundaries

- Image sources are validated but never fetched or executed by MAPLE.
- Base64 data is syntax-checked and bounded; decoded bytes are not interpreted
  as an executable format.
- Provider adapters fail closed when a source form is unsupported rather than
  silently fetching or dropping a part.
- Durable persistence retains the bounded source reference, not a fetched
  copy or provider response.
- Image capability declarations do not claim model quality, semantic image
  understanding, or support for audio/video.

## Invalidation triggers

Reopen this decision if hosts require local media storage, URL fetching,
automatic resizing/transcoding, audio/video content, image output, or a
provider-neutral remote media service. Those changes require a separate
network/security and quota contract.
