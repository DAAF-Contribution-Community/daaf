// Synthetic pdf_ingest fixture: a full-page raster image with a text layer
// drawn over it, standing in for a scanned page that already carries an
// (often noisy) OCR text layer. Two extractors read the same layer and agree,
// so agreement cannot catch it; pdf_ingest flags it ocr_layer_suspected.
// The overlay text imitates OCR noise (0 for O, 1 for l). Invented text only.
#set document(title: "pdf_ingest fixture: OCR layer over an image", date: none)
#set page(paper: "us-letter", margin: 0pt)
#set text(font: "DejaVu Sans", size: 9pt, lang: "en", hyphenate: false)

#place(top + left, image("../img/scan_source.png", width: 100%, height: 100%))
#place(top + left, dx: 1in, dy: 7.6in, block(width: 6.5in)[
  SYNTHETIC SCAN PAGE LANTERN 4821 0TTER 39O7 MEAD0W 1265 The quiet harb0ur
  kept 58 copper boats. This 1ayer imitates an old OCR pass that misread a few
  letters as digits and a few digits as letters, the way older scanned
  government reports often do, while still covering the whole page image.
])
