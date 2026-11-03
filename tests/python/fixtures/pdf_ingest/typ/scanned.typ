// Synthetic pdf_ingest fixture: an image-only ("scanned") page. The page is a
// single full-page raster (../img/scan_source.png) with no text layer, so
// pdftotext returns only a form feed and the OCR lane must recover the words.
#set document(title: "pdf_ingest fixture: scanned", date: none)
#set page(paper: "us-letter", margin: 0pt)

#image("../img/scan_source.png", width: 100%, height: 100%)
