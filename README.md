Tofu font
=========
[![CI badge][]][CI]

[Tofu font][] provides tiny final-fallback fonts which display unsupported characters as a visible [`.notdef`
glyph][wikipedia], "tofu". They are designed to be embedded in application binaries.

`Tofu.ttf` is only 688 bytes. Its `cmap` is intentionally empty and it only contains a single glyph for `.notdef`. An
application must explicitly select Tofu as its final fallback and shape missing characters to glyph ID 0.

`Tofu-Mono.ttf` is 2,324 bytes and intended for fixed-cell rendering such as terminals. It uses a `cmap` format 13
subtable to select a fullwidth or halfwidth tofu glyphs for fitting to the character width.

Preview of Tofu-Mono font:

<img src="https://github.com/rhysd/ss/blob/master/tofu-font/tofu-mono-preview.png?raw=true" width="1024" height="462" alt="Preview text rendered with Tofu-Mono"/>

## Download

Download `tofu-font.zip` from the latest release on the [releases page][releases].

Alternatively generate `Tofu.ttf` and `Tofu-Mono.ttf` following the instructions in the Development section below.

## Comparison with existing fonts

- [Adobe NotDef][] is a font for the same purpose as Tofu. It explicitly maps 1,111,998 Unicode code points through
  `cmap` formats 4 and 12 to 2,048 non-zero tofu glyphs. Tofu is smaller because it has an empty `cmap` and only glyph
  ID 0.
- [Last Resort][] is a font for a similar purpose to Tofu. It includes a collection of glyphs representing different
  Unicode character ranges. Last Resort High-Efficiency uses [cmap format 13][] but still contains hundreds of glyphs.

| Font | Version | Size (bytes) |
|-|-|-:|
| Tofu.ttf | 1.0.0 | 688 |
| Tofu-Mono.ttf | 1.0.0 | 2,324 |
| AND-Regular.otf | 1.001 | 20,896 |
| AND-Regular.ttf | 1.001 | 219,320 |
| LastResortHE-Regular.ttf | 18.000 | 587,864 |
| LastResort-Regular.ttf | 18.000 | 9,592,228 |

## License

`Tofu.ttf` is derived from [Adobe NotDef][]. `Tofu-Mono.ttf` is derived from [Adobe NotDef][] and [Last Resort][].
They are distributed under the SIL Open Font License v1.1. See the [LICENSE file](./LICENSE) for details.
Always include the LICENSE file when redistributing either font.

## Development

```sh
# Clone this repository
git clone --recursive https://github.com/rhysd/tofu-font.git

# Install dependencies. Using venv is recommended
python -m venv venv
source ./venv/bin/activate
pip install -r ./requirements.txt

# Generate both TTF font files in ./dist directory
python ./generate.py

# Run tests for the generated font
python ./test.py

# Check Python source code with ruff
bash ./check.bash
```

[Tofu font]: https://github.com/rhysd/tofu-font
[wikipedia]: https://en.wikipedia.org/wiki/Notdef_glyph
[releases]: https://github.com/rhysd/tofu-font/releases
[Adobe NotDef]: https://github.com/adobe-fonts/adobe-notdef
[Last Resort]: https://github.com/unicode-org/last-resort-font
[cmap format 13]: https://learn.microsoft.com/en-us/typography/opentype/spec/cmap#format-13-many-to-one-range-mappings
[CI]: https://github.com/rhysd/tofu-font/actions/workflows/ci.yml
[CI badge]: https://github.com/rhysd/tofu-font/actions/workflows/ci.yml/badge.svg
