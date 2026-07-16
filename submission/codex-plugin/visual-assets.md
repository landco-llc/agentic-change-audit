# Visual assets

## Status

**No approved logo exists.** Logo status: `PENDING APPROVED ASSET`.

The OpenAI submission form requires a logo. This task does not produce one, and the submission cannot be completed until an approved asset exists.

## Why no asset is included here

- Asset creation is a **separate lane** with its own approval. It is not part of this documentation package.
- **No placeholder, no generated image, and no improvised mark may be submitted without approval.** An unapproved asset that reaches a public listing is a brand and trademark problem, not a cosmetic one.
- The current Plugin manifest declares no visual asset field, and it **must remain unchanged**. `plugin.json` has no `icon`, `logo`, `assets`, `screenshots`, or `banner` key, and `validate-codex-plugin.py` rejects any of them. Adding an asset reference is a separate, later change.

## Before creating any asset

The exact size, format, aspect ratio, background, and file requirements **must be reconfirmed against the current OpenAI submission form immediately before asset creation**. Requirements published by any third party, cached in this repository, or remembered from a previous submission are not authoritative and may be stale.

Do not begin production from the requirements as understood today. Re-read the form first.

## Screenshot rules

If screenshots are produced for the listing, each one must contain:

- no private repository name, path, or content;
- no account name, avatar, organization name, or email address;
- no local filesystem path;
- no unrelated Plugin, extension, or marketplace listing;
- no token, credential, or secret in any visible terminal, editor, or browser pane.

Screenshots are public artifacts. Capture them from a purpose-built public example, not from a working environment.

## Human gate

Logo approval is tracked as a `PENDING HUMAN CHECK` item in [human-prerequisites.md](human-prerequisites.md). It is not satisfied by this package.
