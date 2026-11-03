// Synthetic pdf_ingest fixture: a five-page document combining several cases
// under a repeated running header and a "Page N of M" footer:
//   page 1  single-column prose with a planted unique quote
//   page 2  two columns, with a real compound hyphen at a line break
//   page 3  a ruled table with a "Table 1" caption
//   page 4  a figure (embedded raster) with a "Figure 1" caption
//   page 5  an image-only (scanned) page; only the header and footer are text
// Every word and number is invented for DAAF's tests (no third-party text).
#set document(title: "pdf_ingest fixture: multipage", date: none)
#set page(
  paper: "us-letter",
  margin: (x: 1in, top: 1.2in, bottom: 1.2in),
  header: align(center)[Synthetic Journal of Fixture Studies, Volume 7],
  footer: context align(center)[Page #counter(page).display() of #counter(page).final().first()],
)
#set text(font: "Libertinus Serif", size: 11pt, lang: "en", hyphenate: false)
#set par(justify: false)

= Multipage Fixture

The first page of the combined fixture holds plain prose. Its planted sentence
is: "The violet ferry carried nineteen patient cartographers across the silver
estuary." That sentence appears on this page and nowhere else.

The rest of the page describes the imaginary voyage. The cartographers drew
the coastline twice, once at low tide and once at high tide, and argued about
which drawing should go into the final atlas. They settled the matter by
drawing a third map that showed both tides at once.

#pagebreak()

#columns(2, gutter: 0.35in)[
  The second page is set in two columns. Its method paragraph relies on
  natural-\
  language summaries of each imaginary voyage, written by the cartographers
  themselves after they returned to port.

  The summaries were short, rarely more than a paragraph, and each one named the
  weather, the tide and the number of gulls seen from the deck.

  #colbreak()

  The right column notes that the summaries disagreed about the gulls more than
  about anything else. The planted phrase for this column is: "the harbour
  pilot counted gulls in threes and rounded every total down."
]

#pagebreak()

#figure(
  table(
    columns: 3,
    stroke: 0.6pt,
    align: right,
    [], [Low tide], [High tide],
    [Gulls], [14], [-3],
    [], [(2.1)], [(0.8)],
    [Boats], [27], [31],
    [], [(4.4)], [(5.0)],
  ),
  caption: [Invented counts from the imaginary voyage],
)

The table above is invented and exists only to exercise the table flag.

#pagebreak()

#figure(
  image("../img/figure_art.png", width: 70%),
  caption: [Invented bar heights from the imaginary voyage],
)

#pagebreak()

#image("../img/scan_source.png", height: 100%)
