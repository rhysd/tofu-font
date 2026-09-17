#!/usr/bin/env python3
"""Validate the generated Tofu font in ./dist."""

from io import BytesIO
from pathlib import Path
import struct
import unittest

from fontTools.pens.recordingPen import RecordingPen
from fontTools.ttLib import TTFont
import uharfbuzz as hb

import generate


ROOT = Path(__file__).resolve().parent
FONT_PATH = ROOT / "dist" / "Tofu.ttf"
EXPECTED_TABLES = {
    "OS/2",
    "cmap",
    "glyf",
    "head",
    "hhea",
    "hmtx",
    "loca",
    "maxp",
    "name",
    "post",
}


def _record_glyph(font: TTFont, glyph_name: str):
    pen = RecordingPen()
    font.getGlyphSet()[glyph_name].draw(pen)
    return pen.value


def _sfnt_checksum(data: bytes) -> int:
    padding = (-len(data)) % 4
    if padding:
        data += b"\0" * padding
    return sum(struct.unpack(f">{len(data) // 4}I", data)) & 0xFFFFFFFF


def _shape(font_bytes: bytes, text: str):
    """Shape text as an application would when Tofu is the final fallback."""
    face = hb.Face(font_bytes)
    font = hb.Font(face)
    font.scale = (face.upem, face.upem)
    buffer = hb.Buffer()
    buffer.add_str(text)
    buffer.guess_segment_properties()
    hb.shape(font, buffer)
    return list(zip(buffer.glyph_infos, buffer.glyph_positions))


class TofuFontTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not FONT_PATH.is_file():
            raise RuntimeError(
                f"Generated font does not exist: {FONT_PATH}. Run `python ./generate.py` before running the tests."
            )
        cls.font_bytes = FONT_PATH.read_bytes()
        cls.font = TTFont(
            BytesIO(cls.font_bytes), recalcTimestamp=False, lazy=False
        )
        cls.source = TTFont(
            generate.SOURCE_FILE, recalcTimestamp=False, lazy=False
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.font.close()
        cls.source.close()

    def test_has_only_required_tables(self) -> None:
        self.assertEqual(set(self.font.keys()) - {"GlyphOrder"}, EXPECTED_TABLES)

    def test_has_exactly_one_glyph(self) -> None:
        self.assertEqual(self.font["maxp"].numGlyphs, 1)
        self.assertEqual(self.font.getGlyphOrder(), [".notdef"])

    def test_cmap_is_empty(self) -> None:
        self.assertEqual(self.font.getBestCmap(), {})
        self.assertTrue(self.font["cmap"].tables)
        for table in self.font["cmap"].tables:
            self.assertEqual(table.cmap, {})

    def test_outline_matches_adobe_notdef(self) -> None:
        self.assertEqual(
            _record_glyph(self.font, ".notdef"),
            _record_glyph(self.source, ".notdef"),
        )
        glyph = self.font["glyf"][".notdef"]
        self.assertEqual(glyph.numberOfContours, 5)
        self.assertEqual(
            (glyph.xMin, glyph.yMin, glyph.xMax, glyph.yMax),
            (100, -120, 900, 880),
        )

    def test_glyph_has_no_hinting(self) -> None:
        glyph = self.font["glyf"][".notdef"]
        bytecode = glyph.program.getBytecode() if hasattr(glyph, "program") else b""
        self.assertEqual(bytecode, b"")

    def test_metrics_match_adobe_notdef(self) -> None:
        self.assertEqual(self.font["head"].unitsPerEm, 1000)
        self.assertEqual(self.font["hmtx"][".notdef"], (1000, 100))
        self.assertEqual(self.font["hhea"].ascent, 880)
        self.assertEqual(self.font["hhea"].descent, -120)

    def test_font_names(self) -> None:
        names = self.font["name"]
        self.assertEqual({record.nameID for record in names.names}, {1, 2, 4, 6})
        self.assertEqual(names.getDebugName(1), "Tofu")
        self.assertEqual(names.getDebugName(2), "Regular")
        self.assertEqual(names.getDebugName(4), "Tofu Regular")
        self.assertEqual(names.getDebugName(6), "Tofu-Regular")

    def test_embedding_is_unrestricted(self) -> None:
        self.assertEqual(self.font["OS/2"].fsType, 0)

    def test_generation_is_reproducible(self) -> None:
        self.assertEqual(self.font_bytes, generate.build_font())

    def test_font_is_small(self) -> None:
        self.assertLessEqual(len(self.font_bytes), 4096)

    def test_sfnt_checksum_is_valid(self) -> None:
        self.assertEqual(_sfnt_checksum(self.font_bytes), 0xB1B0AFBA)

    def test_mixed_real_world_text_shapes_to_tofu(self) -> None:
        for text in ("Hello, \u4e16\u754c \U0001f44b", "\u0645\u0631\u062d\u0628\u0627"):
            with self.subTest(text=text):
                shaped = _shape(self.font_bytes, text)
                self.assertEqual(
                    [info.codepoint for info, _ in shaped], [0] * len(text)
                )
                self.assertEqual(
                    [pos.x_advance for _, pos in shaped], [1000] * len(text)
                )

    def test_unicode_edge_cases_shape_to_tofu(self) -> None:
        # Latin, Japanese, an emoji, the replacement character, and the last
        # Unicode scalar value exercise the kinds of misses seen in practice.
        text = "A\u3042\U0001f600\ufffd\U0010ffff"
        shaped = _shape(self.font_bytes, text)

        self.assertEqual([info.codepoint for info, _ in shaped], [0] * len(text))
        self.assertEqual([pos.x_advance for _, pos in shaped], [1000] * len(text))

    def test_spaces_are_visible_tofu(self) -> None:
        # Include ASCII whitespace, no-break space, and ideographic space.
        shaped = _shape(self.font_bytes, " \t\u00a0\u3000")

        self.assertEqual([info.codepoint for info, _ in shaped], [0] * 4)
        self.assertEqual([pos.x_advance for _, pos in shaped], [1000] * 4)

    def test_default_ignorables_do_not_produce_tofu(self) -> None:
        # These formatting characters must remain invisible even though the
        # font deliberately displays missing printable characters.
        text = "\u200c\u200d\u2060\ufe0f"
        self.assertEqual(_shape(self.font_bytes, text), [])

    def test_default_ignorables_are_removed_from_real_text(self) -> None:
        # A ZWJ/variation selector sequence cannot form an emoji ligature in
        # this font. HarfBuzz should drop the controls and retain one tofu for
        # each visible code point. Cluster IDs are deliberately not asserted:
        # shapers normally merge emoji-sequence components into one cluster.
        text = "A\u200d\U0001f469\ufe0f B"
        shaped = _shape(self.font_bytes, text)

        self.assertEqual([info.codepoint for info, _ in shaped], [0, 0, 0, 0])
        self.assertEqual([pos.x_advance for _, pos in shaped], [1000] * 4)

    def test_combining_character_still_resolves_to_tofu(self) -> None:
        # HarfBuzz positions a combining mark over the preceding cell and
        # gives it zero advance but it must still resolve to the tofu glyph.
        shaped = _shape(self.font_bytes, "e\u0301")

        self.assertEqual([info.codepoint for info, _ in shaped], [0, 0])
        self.assertEqual([pos.x_advance for _, pos in shaped], [1000, 0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
