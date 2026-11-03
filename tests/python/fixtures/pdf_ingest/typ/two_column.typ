// Synthetic pdf_ingest fixture: a two-column page. The left column breaks a
// real compound word at its hyphen ("natural-" / "language") and a plain word
// at a soft line-break hyphen ("experi-" / "mental"); both breaks are forced
// with a typst line break so they land at a line end on every typst version.
// Every word is invented for DAAF's tests (no third-party text).
#set document(title: "pdf_ingest fixture: two column", date: none)
#set page(paper: "us-letter", margin: 0.8in, columns: 2)
#set columns(gutter: 0.35in)
#set text(font: "Libertinus Serif", size: 10.5pt, lang: "en", hyphenate: false)
#set par(justify: false)

= Two-Column Fixture

The left column describes a small study of tidal notebooks. The method relies
on natural-\
language processing of short synthetic field notes written by imaginary
surveyors, and an experi-\
mental tagging pass that marks each note with a weather label.

The notes were sorted by harbour, by week and by the colour of the notebook
cover. Each surveyor wrote in pencil, and the pencil marks were transcribed by
hand before any counting began. The left column ends here.

#colbreak()

The right column reports what the imaginary surveyors found. Calm mornings
were more common than stormy ones, and the notebooks with green covers held
the longest entries. The right column closes with a planted phrase: "the
lantern keeper filed every chart under a different constellation."

Nothing in this column is real data; it exists so that the two extractors can
be compared on a page whose reading order depends on column detection.
