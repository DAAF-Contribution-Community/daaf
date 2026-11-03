// Synthetic pdf_ingest fixture: a figure page with a large embedded raster
// image (well over 5% of the page width and height) and a "Figure 1" caption.
// Every word is invented for DAAF's tests (no third-party text).
#set document(title: "pdf_ingest fixture: figure", date: none)
#set page(paper: "us-letter", margin: 1in)
#set text(font: "Libertinus Serif", size: 11pt, lang: "en", hyphenate: false)
#set par(justify: false)

= Figure Fixture

The figure below shows invented bar heights for five imaginary harbours. It is
an embedded raster image, so the text layer holds only this paragraph and the
caption, and the ingest tool should flag the page as needing a visual check.

#figure(
  image("../img/figure_art.png", width: 75%),
  caption: [Invented bar heights for five imaginary harbours],
)

The paragraph after the figure repeats that none of these values are real.
