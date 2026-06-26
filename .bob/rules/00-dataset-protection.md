# Dataset Protection Rule

**NEVER edit files in the `dataset/` directory.**

## Why This Rule Exists

The dataset is **FIXED input** per AGENTS.md requirements. It represents the challenge constraints and must remain unchanged throughout development.

## Protected Files

- **`partners.json`** - The portfolio to assess (22 companies, 53 products)
- **`taxonomy.json`** - Authoritative enums for categories, substances, regulation families
- **`regulatory_updates.json`** - EXAMPLE rules showing shape only (NOT an answer key)
- **`sample_expected_output.json`** - Example Finding structure
- **`partners.csv`** - Flattened portfolio (same as partners.json)
- **`dataset_stats.json`** - Summary counts
- **`feed/*.html`** - Example HTML notices

## What These Files Are

- **Read-only reference** - Use them to understand data structures
- **Test fixtures** - Use them to validate your logic
- **Shape examples** - Learn the format, but fetch LIVE data

## What These Files Are NOT

- **NOT an answer key** - Don't match findings against regulatory_updates.json
- **NOT a data source** - Rules must come from live EUR-Lex/CELLAR/ECHA
- **NOT modifiable** - Any changes break the challenge constraints

## Ground Truth

Only 5 partners have `compliance_status` with seeded gaps:
- **P006 FitTrack** - PFAS/PFHxA coating (REACH)
- **P008 PlayBright** - DEHP limit + button-cell security (GPSR)
- **P010 DisplayOne** - Mercury in CCFL panel (RoHS)
- **P013 RideVolt** - Missing battery passport (Battery Reg)
- **P022 KidVision** - Micro-USB + RED cybersecurity

Use these to **validate** your gap engine, not as the only gaps to find.

## Consequences of Violation

- Breaks challenge requirements
- Invalidates test results
- Fails judging criteria
- Loses points for "Quality of insight"

## Correct Approach

✅ **DO:**
- Read dataset files to understand structure
- Use taxonomy.json enums in your code
- Test against the 5 seeded gaps
- Fetch LIVE rules from EUR-Lex/CELLAR/ECHA

❌ **DON'T:**
- Modify any file in dataset/
- Match findings against regulatory_updates.json
- Add/remove partners or products
- Change taxonomy enums without team discussion

## Exception

The **ONLY** exception is if the team collectively decides to add a new category/substance/family to `taxonomy.json` - but this requires:
1. Team discussion and agreement
2. Updating all dependent code
3. Documenting the change
4. Ensuring it doesn't break existing logic
