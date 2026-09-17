Tofu font
=========

[Tofu font][] is a special-purpose font that contains a single [`.notdef` glyph][wikipedia], "tofu". Its `cmap` is
intentionally empty. When an application explicitly selects `.notdef` glyph as its final fallback and shapes text,
unsupported visible characters resolve to the `.notdef` glyph. Tofu is designed to be embedded in an application binary
and is only 688 bytes.

Because the empty `cmap` advertises no character coverage, the application must explicitly select Tofu and must be able
to shape missing characters to glyph ID 0.

## Download

Download `tofu-font.zip` from the latest release on the [releases page][releases].

Alternatively, generate `Tofu.ttf` as described in the Development section below.

## Comparison with existing fonts

- [Adobe NotDef][] is a font for the same purpose as Tofu. It explicitly maps 1,111,998 Unicode code points through
  `cmap` formats 4 and 12 to 2,048 non-zero tofu glyphs. Tofu is smaller because it has an empty `cmap` and only glyph
  ID 0.
- [Last Resort][] is a font for a similar purpose to Tofu. It includes a collection of glyphs representing different
  Unicode character ranges. Last Resort High-Efficiency uses [cmap format 13][format-13] but still contains hundreds
  of glyphs.

| Font | Version | Size (bytes) |
|-|-|-:|
| Tofu.ttf | Current build | 688 |
| AND-Regular.otf | 1.001 | 20,896 |
| AND-Regular.ttf | 1.001 | 219,320 |
| LastResortHE-Regular.ttf | 18.000 (Unicode 18.0.0) | 587,864 |
| LastResort-Regular.ttf | 18.000 (Unicode 18.0.0) | 9,592,228 |

## License

This font is derived from [Adobe NotDef][] and is distributed under the same license, the SIL Open Font License v1.1.
See the [LICENSE file](./LICENSE) for details. Always include the LICENSE file when redistributing `Tofu.ttf`.

## Development

```sh
# Clone this repository
git clone --recursive https://github.com/rhysd/tofu-font.git

# Install dependencies. Using venv is recommended
python -m venv venv
source ./venv/bin/activate
pip install -r ./requirements.txt

# Generate the TTF font file in ./dist directory
python ./generate.py

# Run tests for the generated font
python ./test.py

# Check Python source code with ruff
bash ./check.bash
```

[Tofu font]: https://github.com/rhysd/tofu-font
[wikipedia]: https://en.wikipedia.org/wiki/Notdef_glyph
[format-13]: https://learn.microsoft.com/en-us/typography/opentype/spec/cmap#format-13-many-to-one-range-mappings
[releases]: https://github.com/rhysd/tofu-font/releases
[Adobe NotDef]: https://github.com/adobe-fonts/adobe-notdef
[Last Resort]: https://github.com/unicode-org/last-resort-font
