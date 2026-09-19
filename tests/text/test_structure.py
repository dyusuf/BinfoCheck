import pytest

from binfocheck.text.structure import scan


def test_structure_and_locations() -> None:
    text = (
        "# Titel\r\n\r\nÄpfel 🍎 sind rot.\r\nWeiter.  \r\n\r\n- Erstens.\r\n"
        "- Zweitens\r\n  Fortsetzung.\r\n\r\nUntertitel\r\n===\r\n"
    )
    blocks = scan(text)
    assert [b.kind for b in blocks] == ["heading", "paragraph", "bullet", "bullet", "heading"]
    assert [text[b.start : b.end] for b in blocks] == [
        "# Titel",
        "Äpfel 🍎 sind rot.\r\nWeiter.  ",
        "- Erstens.",
        "- Zweitens\r\n  Fortsetzung.",
        "Untertitel\r\n===",
    ]
    assert [b.level for b in blocks] == [1, None, None, None, 1]
    assert text[blocks[2].content_start : blocks[2].end] == "Erstens."


@pytest.mark.parametrize(
    "text",
    [
        "```text\n# Nicht Heading\n- Nicht Liste\n\nSatz. Satz.\n```",
        "~~~\nCode.\n~~~",
        "| A | B |\n|---|---|\n| X. | Y. |",
        "<div>\n# Kein Heading\nText.\n</div>",
        "<div>\n\n# Kein Heading\n\nText.\n</div>",
        "<!--\n\n# Kein Heading\n-->",
        "<div>\n\n# Unclosed",
        "- <span>Complex.</span>\n- Next.",
        "- Outer\n  - Nested\n- Next",
        "> Quote.\n> Next.",
        "    code.\n    next.",
    ],
)
def test_complex_blocks_remain_opaque(text: str) -> None:
    blocks = scan(text)
    assert len(blocks) == 1
    assert blocks[0].opaque and blocks[0].kind == "paragraph"
    assert text[blocks[0].start : blocks[0].end] == text


def test_ordered_markers_not_decimals_or_bold_headings() -> None:
    text = "1. Eins\n2) Zwei\n\n3.5 bleibt ein Wert.\n\n**Nur fett**"
    assert [b.kind for b in scan(text)] == ["bullet", "bullet", "paragraph", "paragraph"]
