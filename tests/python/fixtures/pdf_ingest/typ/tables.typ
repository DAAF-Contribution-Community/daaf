// Synthetic pdf_ingest fixture: a table page. Table 1 is fully ruled (every
// cell stroked), so pdfplumber's default "lines" strategy should find it.
// Table 2 is borderless booktabs style (three horizontal rules, no vertical
// lines), so only the caption regex should flag it. Negative numbers are
// typed with an ASCII "-", which typst typesets as U+2212 MINUS SIGN.
// Standard errors sit in parentheses; stars mark invented significance.
// All numbers are invented for DAAF's tests (no third-party data).
#set document(title: "pdf_ingest fixture: tables", date: none)
#set page(paper: "us-letter", margin: 1in)
#set text(font: "Libertinus Serif", size: 10pt, lang: "en", hyphenate: false)

#figure(
  table(
    columns: 4,
    stroke: 0.6pt,
    align: right,
    [], [(1)], [(2)], [(3)],
    [T], [0.123\*\*\*], [-0.087\*], [0.041],
    [], [(0.031)], [(0.044)], [(0.052)],
    [X1], [-1.502\*\*], [0.338], [-0.019],
    [], [(0.611)], [(0.274)], [(0.008)],
    [X2], [2.917], [-0.446\*\*\*], [0.775\*],
    [], [(1.804)], [(0.102)], [(0.391)],
    [N], [1,204], [1,198], [1,187],
    [R2], [0.214], [0.236], [0.251],
  ),
  caption: [Invented estimates, ruled],
)

#figure(
  table(
    columns: 4,
    stroke: none,
    align: right,
    table.hline(stroke: 1pt),
    [], [2019], [2020], [2021],
    table.hline(stroke: 0.5pt),
    [A], [12.5], [-3.75], [48.06],
    [], [(1.12)], [(0.96)], [(5.31)],
    [B], [0.07], [-0.66], [19.42],
    [], [(0.02)], [(0.31)], [(2.08)],
    [C], [305.1], [-27.9], [6.003],
    [], [(41.7)], [(8.84)], [(0.912)],
    table.hline(stroke: 1pt),
  ),
  caption: [Invented values, booktabs],
)
