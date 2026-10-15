// Source drawing for the figure fixture: coloured shapes, no text. Rendered
// to ../img/figure_art.png by ../generate_fixtures.py (pdftoppm), then
// embedded as an image by figure.typ and multipage.typ.
#set document(title: "pdf_ingest fixture source: figure art", date: none)
#set page(width: 4in, height: 3in, margin: 0.2in, fill: white)

#place(top + left, dx: 0.1in, dy: 1.6in, rect(width: 0.5in, height: 0.9in, fill: rgb("#3b6ea8")))
#place(top + left, dx: 0.8in, dy: 0.9in, rect(width: 0.5in, height: 1.6in, fill: rgb("#d9822b")))
#place(top + left, dx: 1.5in, dy: 1.3in, rect(width: 0.5in, height: 1.2in, fill: rgb("#5aa469")))
#place(top + left, dx: 2.2in, dy: 0.5in, rect(width: 0.5in, height: 2.0in, fill: rgb("#a83b6e")))
#place(top + left, dx: 2.9in, dy: 0.3in, circle(radius: 0.3in, fill: rgb("#e8c547")))
#place(top + left, dx: 0.0in, dy: 2.55in, line(length: 3.6in, stroke: 1.5pt))
