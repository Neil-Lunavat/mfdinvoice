"""The distributor's own invoice, laid out and drawn on this PC.

Anyone already part-way through a financial year on their own invoice series cannot switch to the registrar's
numbering, so the app draws their own invoice instead, in their format and number series, from the registrar's figures.

    fonts      Arial's character widths, so a text is measured exactly as Arial draws it
    money      rupees as Tally prints them: 1,23,456.78 and "Indian Rupees ... Only"
    templates  each invoice format as data: `tally` is the Tally standard print
    layout     a template plus one invoice's facts, turned into a draw-list (`hands/ops_pdf.render` draws it)
    parties    the fund house's name, GSTIN and address, read off the registrar's own invoice
    sample     an example invoice, for the preview in setup and Settings
"""
