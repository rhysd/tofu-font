"""Validate the generated Tofu font in ./dist."""

import copy
import plistlib
import struct
import unittest
import xml.etree.ElementTree as ET
from io import BytesIO
from pathlib import Path

import uharfbuzz as hb
import unicodedata2
from fontTools.misc.roundTools import otRound
from fontTools.pens.recordingPen import RecordingPen
from fontTools.ttLib import TTFont

import generate

ROOT = Path(__file__).resolve().parent
FONT_PATH = ROOT / "dist" / "Tofu.ttf"
MONO_FONT_PATH = ROOT / "dist" / "Tofu-Mono.ttf"
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
        cls.font = TTFont(BytesIO(cls.font_bytes), recalcTimestamp=False, lazy=False)
        cls.source = TTFont(
            generate.ADOBE_NOTDEF_FILE, recalcTimestamp=False, lazy=False
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
        for text in (
            "Hello, \u4e16\u754c \U0001f44b",
            "\u0645\u0631\u062d\u0628\u0627",
        ):
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


class TofuMonoFontTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not MONO_FONT_PATH.is_file():
            raise RuntimeError(
                f"Generated font does not exist: {MONO_FONT_PATH}. Run `python ./generate.py` before running the tests."
            )
        cls.font_bytes = MONO_FONT_PATH.read_bytes()
        cls.font = TTFont(BytesIO(cls.font_bytes), recalcTimestamp=False, lazy=False)
        cls.source = TTFont(
            generate.ADOBE_NOTDEF_FILE, recalcTimestamp=False, lazy=False
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.font.close()
        cls.source.close()

    def glyph_id_for(self, character: str) -> int:
        glyph_name = self.font.getBestCmap().get(ord(character), ".notdef")
        return self.font.getGlyphID(glyph_name)

    def test_has_only_required_tables(self) -> None:
        self.assertEqual(set(self.font.keys()) - {"GlyphOrder"}, EXPECTED_TABLES)

    def test_has_two_tofu_glyphs_and_one_blank_space(self) -> None:
        self.assertEqual(self.font["maxp"].numGlyphs, 3)
        self.assertEqual(self.font.getGlyphID(".notdef"), 0)
        self.assertEqual(self.font.getGlyphID("space"), 2)
        self.assertEqual(self.font["glyf"]["space"].numberOfContours, 0)

    def test_fullwidth_outline_matches_adobe_notdef(self) -> None:
        self.assertEqual(
            _record_glyph(self.font, ".notdef"),
            _record_glyph(self.source, ".notdef"),
        )
        self.assertEqual(self.font["hmtx"][".notdef"], (1000, 100))

    def test_halfwidth_outline_matches_last_resort_metrics(self) -> None:
        glyph_name = self.font.getGlyphName(1)
        glyph = self.font["glyf"][glyph_name]

        font_info = plistlib.loads(generate.LAST_RESORT_INFO_FILE.read_bytes())
        source_units_per_em = font_info["unitsPerEm"]
        source_glyph = ET.parse(generate.LAST_RESORT_FILE).getroot()
        source_advance = int(source_glyph.find("advance").attrib["width"])
        scale = self.font["head"].unitsPerEm / source_units_per_em
        expected_coordinates = []
        expected_end_points = []
        for contour in source_glyph.findall("./outline/contour"):
            for point in contour.findall("point"):
                expected_coordinates.append(
                    (
                        otRound(int(point.attrib["x"]) * scale),
                        otRound(int(point.attrib["y"]) * scale),
                    )
                )
            expected_end_points.append(len(expected_coordinates) - 1)

        self.assertEqual(source_advance * 2, source_units_per_em)
        expected_advance = otRound(source_advance * scale)
        expected_left_side_bearing = min(x for x, _ in expected_coordinates)
        self.assertEqual(
            self.font["hmtx"][glyph_name],
            (expected_advance, expected_left_side_bearing),
        )
        self.assertEqual(list(glyph.coordinates), expected_coordinates)
        self.assertEqual(glyph.endPtsOfContours, expected_end_points)
        self.assertTrue(all(flag & 1 for flag in glyph.flags))

    def test_uses_unicode_format_13_cmap(self) -> None:
        tables = self.font["cmap"].tables
        self.assertEqual(len(tables), 1)
        self.assertEqual(
            (tables[0].format, tables[0].platformID, tables[0].platEncID),
            (13, 0, 6),
        )
        self.assertEqual(tables[0].nGroups, 132)
        self.assertTrue(self.font["head"].flags & (1 << 14))

    def test_direct_lookup_uses_halfwidth_tofu(self) -> None:
        # ASCII, neutral-width Arabic, and halfwidth katakana exercise the
        # direct cmap lookup used by nuv's fast path.
        font = hb.Font(hb.Face(self.font_bytes))
        for character in ("A", "\u0645", "\uff61"):
            with self.subTest(character=character):
                self.assertEqual(self.glyph_id_for(character), 1)
                self.assertEqual(font.get_nominal_glyph(ord(character)), 1)

    def test_wide_characters_use_fullwidth_tofu(self) -> None:
        for character in ("\u3042", "\U0001f600"):
            with self.subTest(character=character):
                self.assertEqual(self.glyph_id_for(character), 0)

    def test_ambiguous_width_is_chosen_to_minimize_cmap_groups(self) -> None:
        # These A characters connect required-halfwidth ranges.
        for character in ("\u00a1", "\u03b1"):
            with self.subTest(character=character):
                self.assertEqual(self.glyph_id_for(character), 1)

        # These A-only islands are surrounded by wide characters, so omitting
        # them avoids creating extra format 13 groups.
        for character in ("\u26c6", "\ue000"):
            with self.subTest(character=character):
                self.assertEqual(self.glyph_id_for(character), 0)

    def test_default_ignorables_are_not_advertised_by_cmap(self) -> None:
        cmap = self.font.getBestCmap()
        for character in ("\u00ad", "\u200d", "\ufe0f", "\U000e0100"):
            with self.subTest(character=character):
                self.assertNotIn(ord(character), cmap)

    def test_cmap_covers_all_non_ambiguous_widths(self) -> None:
        cmap = self.font.getBestCmap()
        default_ignorables = {
            codepoint
            for start, end in generate.DEFAULT_IGNORABLE_RANGES
            for codepoint in range(start, end + 1)
        }
        errors = []

        for codepoint in range(0x110000):
            glyph_name = cmap.get(codepoint)
            if codepoint == 0x20:
                expected_glyph_id = 2
            elif 0xD800 <= codepoint <= 0xDFFF or codepoint in default_ignorables:
                expected_glyph_id = None
            else:
                width = unicodedata2.east_asian_width(chr(codepoint))
                if width in {"H", "Na", "N"}:
                    expected_glyph_id = 1
                elif width in {"W", "F"}:
                    expected_glyph_id = None
                else:
                    continue

            actual_glyph_id = (
                self.font.getGlyphID(glyph_name) if glyph_name is not None else None
            )
            if actual_glyph_id != expected_glyph_id:
                errors.append(
                    f"U+{codepoint:04X}: expected GID {expected_glyph_id}, got {actual_glyph_id}"
                )
                if len(errors) == 10:
                    break

        self.assertEqual(errors, [])

    def test_real_world_mixed_text_has_cell_sized_advances(self) -> None:
        shaped = _shape(self.font_bytes, "A\uff61\u00a1\u3042\U0001f600")

        self.assertEqual([info.codepoint for info, _ in shaped], [1, 1, 1, 0, 0])
        self.assertEqual(
            [position.x_advance for _, position in shaped],
            [500, 500, 500, 1000, 1000],
        )

    def test_space_is_blank_and_halfwidth(self) -> None:
        shaped = _shape(self.font_bytes, " ")

        self.assertEqual([info.codepoint for info, _ in shaped], [2])
        self.assertEqual([position.x_advance for _, position in shaped], [500])

    def test_default_ignorables_resolve_to_blank_zero_width_glyph(self) -> None:
        shaped = _shape(self.font_bytes, "\u200c\u200d\u2060\ufe0f")

        self.assertEqual([info.codepoint for info, _ in shaped], [2] * 4)
        self.assertEqual([position.x_advance for _, position in shaped], [0] * 4)
        self.assertEqual(self.font["glyf"]["space"].numberOfContours, 0)

    def test_font_names(self) -> None:
        names = self.font["name"]
        self.assertEqual({record.nameID for record in names.names}, {1, 2, 4, 6})
        self.assertEqual(names.getDebugName(1), "Tofu Mono")
        self.assertEqual(names.getDebugName(2), "Regular")
        self.assertEqual(names.getDebugName(4), "Tofu Mono Regular")
        self.assertEqual(names.getDebugName(6), "Tofu-Mono")

    def test_os2_character_coverage_matches_cmap(self) -> None:
        os2 = self.font["OS/2"]
        actual = (
            os2.usFirstCharIndex,
            os2.usLastCharIndex,
            os2.getUnicodeRanges(),
            os2.getCodePageRanges(),
        )

        expected_os2 = copy.copy(os2)
        expected_os2.updateFirstAndLastCharIndex(self.font)
        expected = (
            expected_os2.usFirstCharIndex,
            expected_os2.usLastCharIndex,
            expected_os2.recalcUnicodeRanges(self.font),
            expected_os2.recalcCodePageRanges(self.font),
        )

        self.assertEqual(actual, expected)
        self.assertTrue(actual[2])
        self.assertTrue(actual[3])

    def test_generation_is_reproducible(self) -> None:
        self.assertEqual(self.font_bytes, generate.build_mono_font())

    def test_font_is_small(self) -> None:
        self.assertLessEqual(len(self.font_bytes), 8192)

    def test_sfnt_checksum_is_valid(self) -> None:
        self.assertEqual(_sfnt_checksum(self.font_bytes), 0xB1B0AFBA)


if __name__ == "__main__":
    unittest.main(verbosity=2)
