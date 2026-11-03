// Synthetic pdf_ingest fixture: a page whose body holds a paragraph rotated by
// 90 degrees (non-upright characters, as in a landscape table set sideways on
// a portrait page). The page itself carries no /Rotate attribute; that case
// is pdf/rotate_attr.pdf, which ../generate_fixtures.py derives from
// single_column.pdf with pypdfium2. Every word is invented for DAAF's tests.
#set document(title: "pdf_ingest fixture: rotated text", date: none)
#set page(paper: "us-letter", margin: 1in)
#set text(font: "Libertinus Serif", size: 11pt, lang: "en", hyphenate: false)
#set par(justify: false)

= Rotated Text Fixture

The paragraph below is set sideways. A reader holding the page upright sees it
running from bottom to top, the way a wide table is often printed in a report.

#rotate(-90deg, reflow: true)[
  #block(width: 5in)[
    This sideways paragraph describes an invented survey of lighthouse keepers.
    Each keeper kept a ledger of passing ships, and the ledgers were compared at
    the end of the season to see which harbour had been busiest overall.
  ]
]
