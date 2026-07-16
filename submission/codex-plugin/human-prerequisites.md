# Human prerequisites

Every item below is a human gate. None of them can be satisfied by this repository, by an automated validator, or by an agent.

No item on this list has been completed. Nothing here may be marked done on the basis of an agent's report; the human who performs the step records it.

## Status table

| # | Item | Status |
|---|---|---|
| 1 | OpenAI Platform organization selected | PENDING HUMAN CHECK |
| 2 | Apps Management Write permission | PENDING HUMAN CHECK |
| 3 | L&Co.LLC business identity verification | PENDING HUMAN CHECK |
| 4 | Public website review | PENDING HUMAN CHECK |
| 5 | Support URL review | PENDING HUMAN CHECK |
| 6 | Privacy URL review | PENDING HUMAN CHECK |
| 7 | Terms URL review | PENDING HUMAN CHECK |
| 8 | Availability decision | PENDING HUMAN CHECK |
| 9 | Logo approval | PENDING HUMAN CHECK |
| 10 | Final Skill ZIP upload | PENDING HUMAN CHECK |
| 11 | Submission portal draft creation | PENDING HUMAN CHECK |
| 12 | Policy attestations | PENDING HUMAN CHECK |
| 13 | Final submit decision | PENDING HUMAN CHECK |

## Notes on selected items

**OpenAI Platform organization selected.** The organization that will own the listing has to be chosen before a draft exists, because the draft belongs to it.

**Apps Management Write permission.** The account creating the draft needs this permission in the selected organization. This repository cannot grant or confirm it.

**L&Co.LLC business identity verification.** This is a verification performed by OpenAI against L&Co.LLC. Its state is not known to this repository and must not be asserted anywhere in the submission materials. `listing.json` records it as `PENDING HUMAN CHECK`, and the validator enforces that.

**Public website review, Support URL review, Privacy URL review, Terms URL review.** The URLs in `listing.json` resolve only after this branch is merged into `main`. A human must open each one from the public internet and confirm it renders the intended content before the draft is submitted.

**Availability decision.** `availability.json` records a recommendation, not a decision. The maintainer selects final availability in the submission portal.

**Logo approval.** See [visual-assets.md](visual-assets.md). No approved asset exists.

**Final Skill ZIP upload.** The bundle for submission must be built from a fixed, re-audited commit. No ZIP is produced or published by this package.

**Policy attestations.** Attestations are legal statements about the product. Only an authorized human may make them.

**Final submit decision.** Submission is a deliberate human act. Nothing in this repository triggers it.
