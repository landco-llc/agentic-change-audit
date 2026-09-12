# ACA-W014 Human desktop verification gate

## Purpose

This packet defines the bounded Human desktop verification to be performed only
after ACA-W014 repository preflight has completed its required validation,
independent audit, and any separately authorized Ready/merge step.

It does not authorize release, submission, publication, or any other protected
external effect.

## Fixed desktop candidate binding

Before any Human desktop action, verify all of the following still match:

- repository: `landco-llc/agentic-change-audit`;
- main: `ef88c0e8669e639b06428e5ac55d88b580e14659` unless ACA-W014 itself has
  merged, in which case use the ACA-W014 merge commit only if its resulting tree
  preserves this fixed product/runtime identity;
- product/runtime tree for the current identity:
  `2f7345e83201cfefb67d26853f3ffb2c4655adde`;
- user-facing display name: `ACA - Agentic Change Audit`;
- technical slug / Skill name: `agentic-change-audit`;
- Plugin version: `0.1.0-dev.3`;
- developer/publisher identity: `L&Co.LLC` where required;
- capability: `Read`;
- development preview artifact from Package #85:
  `agentic-change-audit-0.0.0-dev.ef88c0e8669e`;
- development preview SHA-256:
  `211546b87e9824cbff64621dbac229c027162b9aa55d15b37a96b4ab979d4402`.

If any identity, version, capability, artifact binding, effective runtime tree,
or relevant requirement has changed, stop and rebind before continuing.

## Human verification checklist

The authorized Human desktop lane, when separately approved, should verify:

1. The current marketplace/repository source is recognized under the display
   identity `ACA - Agentic Change Audit`.
2. The Plugin is discoverable and presents the exact user-facing display name.
3. The Plugin shows version `0.1.0-dev.3`, capability `Read`, developer
   `L&Co.LLC`, and the expected category/metadata without an unexpected login,
   token, connector, MCP, or write-permission request.
4. Installation completes for the fixed candidate without expanding permissions
   or authentication scope.
5. In a disposable documentation-only repository, explicitly invoke
   `$agentic-change-audit` against a bounded test change.
6. Confirm the invocation remains read-only and returns one supported ACA
   Verdict with fixed base/target identity and evidence limitations as
   applicable.
7. Record repository HEAD and working-tree state immediately before and after
   invocation and confirm no mutation occurred.
8. Capture only public-safe evidence sufficient to prove the displayed current
   identity, installation/invocation behavior, and repository non-mutation.

## Acceptance boundary

A Human desktop PASS for this gate demonstrates only current-identity desktop
presentation, discovery/installation, explicit invocation, and read-only
non-mutation behavior for the exact bound candidate.

It does not by itself authorize or complete:

- Plugin version mutation;
- logo or availability decisions;
- developer/business identity verification;
- Apps Management or OpenAI portal mutation;
- tag or GitHub Release creation;
- final ZIP publication/upload;
- policy attestation;
- public submission, listing, directory publication, or release.

Those remain separate Human/external gates.

## Current gate state

`PENDING HUMAN AUTHORIZATION`.

ACA-W014 repository preflight may prepare and validate this packet, but must not
execute the Human desktop steps without a later explicit Human decision.
