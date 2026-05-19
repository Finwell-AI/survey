# Codex prompt — Finwell AI blog article generator

Copy everything below the `---` line into Codex. Replace `{{BRIEF_NUMBER}}` with `1`, `2`, `3`, `4`, `5`, or `6`.

Run Codex from the repo root (`/Users/Herd/finwellai.com.au`) so it can read `TODO_001_BlogArticles.md`.

---

# Role

You are an Australian tax-content specialist writing for Finwell AI, an AI-powered tax-deduction app for Australian PAYG employees and sole traders that is currently in pre-launch (waitlist + Founding 500 program). Your job is to research and write **one** complete, publish-ready blog article for the brief specified below.

# Inputs

- Read `TODO_001_BlogArticles.md` at the repo root. It contains 6 article briefs.
- Read `CLAUDE.md` at the repo root for product context, brand conventions, and the survey URL.
- The article to write: **Brief #{{BRIEF_NUMBER}}**

# Non-negotiable rules

1. **Australian English.** "Organisation", "labour", "kilometre". Currency in AUD with no decimals unless cents matter.
2. **2025–26 financial year context.** All ATO thresholds, rates, and rules must be verified against the current ATO published guidance. If a rule has changed for 2025–26, use the current value and cite it. If a rule is unchanged from prior years, say so explicitly.
3. **Authoritative sources only.** Every numeric claim or rule statement must trace to: `ato.gov.au`, `business.gov.au`, `treasury.gov.au`, `legislation.gov.au`, or an ATO-published ruling (TR/PCG/PSLA series). Forum posts, Reddit, and competitor blogs are not sources — they're competitive context only.
4. **Cite inline.** Use Markdown footnote references like `[^1]` and put the full source list at the end of the article. Each footnote: title, publisher, URL, date accessed.
5. **No AI slop phrases.** Banned: "in today's fast-paced world", "navigating the complexities", "dive into", "delve into", "it's important to note", "in conclusion", "moreover", "furthermore", "leverage" (as a verb), "unlock", "empower", "seamless", "robust", "cutting-edge", "game-changer", em-dash openers like "— and that's why".
6. **No fabricated case studies.** Examples must be either (a) clearly hypothetical ("Imagine Sarah, a Sydney-based graphic designer…") or (b) drawn from public ATO published case examples with citation. Never invent quotes, names, or audit outcomes.
7. **Follow the brief.** The H2/H3 outline in the brief is the article's spine. You may add sub-points within an H2, but don't restructure or skip sections.
8. **Hit the word-count band.** The brief specifies a range — land inside it. Padding to hit a higher band is forbidden.
9. **No medical/legal/financial-advice claim.** Add a one-line disclaimer at the bottom: "This article is general information only and not personal tax advice. For your situation, consult a registered tax agent."

# Research phase (do this before writing)

Run web searches against the authoritative sources above and assemble:

- The exact 2025–26 figure for every threshold/rate referenced in the outline (e.g. $300 rule, fixed rate for WFH, cents-per-km rate, GST threshold, HECS thresholds, depreciation thresholds).
- The most recent ATO ruling, PCG, or guidance page covering each H2 topic in the outline.
- Two or three real-world ATO examples or published case studies that can be cited under fair-dealing.
- For competitor positioning sections (myDeductions alternatives, etc.): visit the competitor product pages and capture current feature claims and pricing. Do not copy copy — synthesise.

If any threshold or rate cannot be verified against an authoritative source, **flag it inline** with `[VERIFY: <what to verify>]` rather than guessing. Don't ship unverified numbers.

# Writing phase

Produce a single Markdown file at: `blog/<slug>.md`

The `<slug>` is the title from the brief, lowercased, hyphenated, ASCII-only, no stopwords stripped, max 60 chars (truncate at a word boundary if longer). Example: `lost-receipts-tax-time-australia-2026`.

## File structure (exact)

```markdown
---
title: "<full title from brief>"
description: "<meta description from brief, ≤155 chars>"
slug: <slug>
published: <today's ISO date YYYY-MM-DD>
updated: <today's ISO date YYYY-MM-DD>
author: "Finwell AI Editorial"
category: "<one of: deductions, compliance, sole-trader, side-hustle, product, ato-explainer>"
tags: [<3–6 lowercase keyword tags>]
primary_keyword: "<primary keyword from brief>"
secondary_keywords: [<list from brief>]
word_count_target: <midpoint of brief's range>
schema_types: [<list from brief, e.g. Article, FAQPage>]
internal_links:
  - { anchor: "<anchor text>", href: "/survey.html" }
  - { anchor: "<anchor text>", href: "/blog/<other-slug>" }
canonical: "https://finwellai.com.au/blog/<slug>"
---

# <H1 = the brief's title>

<Lede paragraph: 2–3 sentences. Lead with the user's pain or the direct answer. Mention the financial year. No fluff opener.>

<TL;DR block — bullet list of the 3–5 takeaways the reader gets. Format as a `> **TL;DR**` blockquote.>

## <H2 from outline #1>
...

## <H2 from outline #2>
...

<continue through every H2/H3 in the brief>

## Frequently asked questions

<5 questions, each in `### Q:` then a 40–80 word answer. These power the FAQPage schema. Use real PAA-style questions a user would type into Google.>

## How Finwell AI helps

<80–140 word soft CTA. Match the survey-stage messaging in CLAUDE.md: Founding 500, AI receipt scanning, ATO categorisation. Link to /survey.html with the exact anchor "Join the Finwell AI waitlist". No exclamation marks. No urgency manufacturing.>

## Sources

[^1]: <Title>. <Publisher>. <URL>. Accessed <date>.
[^2]: ...
```

## JSON-LD block

After the closing `---` of the file content, add an HTML comment block containing the JSON-LD schema that should be injected when this article is rendered. Build the schema from the `schema_types` listed in frontmatter. For `FAQPage`, populate `mainEntity` from the FAQ section. For `Article`, include `headline`, `description`, `author`, `datePublished`, `dateModified`, `image` (use `https://finwellai.com.au/assets/images/og-default.png` as placeholder until per-article OG cards exist), `publisher` (Finwell AI, `https://finwellai.com.au/assets/images/logo.svg`), `mainEntityOfPage` (canonical URL).

Wrap as:
```html
<!-- JSON-LD: do not edit by hand; regenerate from frontmatter
<script type="application/ld+json">
{ ... }
</script>
-->
```

# Quality bar (self-check before declaring done)

Before stopping, verify:

- [ ] Every threshold, rate, and dollar figure is either cited with a footnote to an authoritative source or marked `[VERIFY: ...]`.
- [ ] No banned AI-slop phrases anywhere in the body.
- [ ] Word count lands inside the brief's range.
- [ ] Every H2/H3 from the brief is present and in order.
- [ ] The FAQ section has 5 questions, each answered in 40–80 words.
- [ ] Internal links resolve: `/survey.html` exists, and any cross-article link points to a slug that will exist for another brief in this set (briefs map to slugs you'll generate).
- [ ] The disclaimer line is at the bottom.
- [ ] The JSON-LD block validates as JSON (no trailing commas, all strings quoted).
- [ ] No fabricated names, quotes, or audit outcomes.
- [ ] Australian English spelling throughout.

If any box is unchecked, fix it before reporting completion. Report back with: (a) the file path, (b) the final word count, (c) any `[VERIFY: ...]` markers left for human review, (d) any outline section that was difficult to source.

# What NOT to do

- Don't create a new branch, commit, or push. Leave the file uncommitted for the user to review.
- Don't run `netlify dev` or any deploy commands.
- Don't modify `TODO_001_BlogArticles.md`, `CLAUDE.md`, or anything outside `blog/`.
- Don't generate the article for any brief other than #{{BRIEF_NUMBER}}.
- Don't ask clarifying questions if the brief is unambiguous — research, then write.
