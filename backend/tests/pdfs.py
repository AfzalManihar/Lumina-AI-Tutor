"""Helpers that build small real PDFs for tests."""
from __future__ import annotations

import io

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def make_pdf(pages: list[str]) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for text in pages:
        y = 800
        for line in text.split("\n"):
            c.drawString(50, y, line)
            y -= 16
        c.showPage()
    c.save()
    return buf.getvalue()


PHOTO_PAGES = [
    "Photosynthesis converts light energy into chemical energy.\nChloroplasts contain chlorophyll which absorbs light.\nThe light reactions occur in the thylakoid membranes.",
    "The Calvin cycle uses ATP and NADPH to fix carbon dioxide into glucose.\nThe Calvin cycle takes place in the stroma of the chloroplast.",
]
HISTORY_PAGES = [
    "The French Revolution began in 1789 with the storming of the Bastille.\nIt abolished the monarchy and established a republic in 1792.",
]
