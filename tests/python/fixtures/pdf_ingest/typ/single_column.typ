// Synthetic pdf_ingest fixture: one single-column page with a planted,
// unique quote. Every word is invented for DAAF's tests (no third-party text).
// Compiled by ../generate_fixtures.py with `quarto typst compile`.
#set document(title: "pdf_ingest fixture: single column", date: none)
#set page(paper: "us-letter", margin: 1in)
#set text(font: "Libertinus Serif", size: 11pt, lang: "en", hyphenate: false)
#set par(justify: false)

= Synthetic Single-Column Fixture

This page exists only to exercise the deterministic PDF ingest tool. It holds
ordinary prose in one column, so both text extractors should read it in the
same order and agree closely on its content.

The planted sentence for quote anchoring is: "The cobalt heron recorded eleven
quiet tides beside the amber lighthouse before dawn." It appears nowhere else
in the fixture set.

A second paragraph keeps the page comfortably above the scanned-page threshold.
The surveyors walked along the gravel path, compared their notes on the weather,
and agreed that the morning had been calm. Nobody counted the gulls, although
several of them circled the harbour wall while the tide turned.

A final paragraph mentions an office, a flagstone floor and an affluent
fisherman, so that the typeface has a chance to draw its usual ligatures.
