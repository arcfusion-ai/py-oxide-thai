"""Generate synthetic, Unicode-mapped PDF fixtures without external fonts."""


def make_mark_font():
    """Build an original tiny TTF with a mark whose ink is left of its origin."""
    from io import BytesIO

    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    builder = FontBuilder(1000, isTTF=True)
    order = [".notdef", "base", "next", "mark"]
    builder.setupGlyphOrder(order)
    builder.setupCharacterMap({ord("ก"): "base", ord("ต"): "next", ord("ิ"): "mark"})
    glyphs = {}
    for name in order:
        pen = TTGlyphPen(None)
        if name != ".notdef":
            left, right, bottom, top = (
                (-300, -100, 700, 800) if name == "mark" else (0, 600, 0, 700)
            )
            pen.moveTo((left, bottom))
            pen.lineTo((right, bottom))
            pen.lineTo((right, top))
            pen.lineTo((left, top))
            pen.closePath()
        glyphs[name] = pen.glyph()
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics(
        {name: (0, -300) if name == "mark" else (600, 0) for name in order}
    )
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupNameTable({"familyName": "SyntheticMark", "styleName": "Regular"})
    builder.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    builder.setupPost()
    builder.setupMaxp()
    builder.font["head"].created = builder.font["head"].modified = 2082844800
    output = BytesIO()
    builder.save(output)
    return output.getvalue()


def make_generic_font(chars):
    """Embed original rectangular glyphs so every reader can load the font."""
    from io import BytesIO

    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    names = {c: f"g{ord(c):04x}" for c in chars}
    order = [".notdef", *names.values()]
    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder(order)
    builder.setupCharacterMap({ord(c): name for c, name in names.items()})
    glyphs, metrics = {}, {".notdef": (600, 0)}
    glyphs[".notdef"] = TTGlyphPen(None).glyph()
    for c, name in names.items():
        pen = TTGlyphPen(None)
        mark = c in "ัิีึืฺุู็่้๊๋์ํ๎"
        if not c.isspace():
            bottom, top = (700, 800) if mark else (0, 700)
            pen.moveTo((-50, bottom))
            pen.lineTo((50, bottom))
            pen.lineTo((50, top))
            pen.lineTo((-50, top))
            pen.closePath()
        glyphs[name] = pen.glyph()
        metrics[name] = (0 if mark else 600, -50)
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics(metrics)
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupNameTable({"familyName": "SyntheticUnicode", "styleName": "Regular"})
    builder.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    builder.setupPost()
    builder.setupMaxp()
    builder.font["head"].created = builder.font["head"].modified = 2082844800
    output = BytesIO()
    builder.save(output)
    return output.getvalue()


def make_pdf(path, runs, font_data=None):
    import zlib
    from io import BytesIO

    from fontTools.ttLib import TTFont

    chars = sorted({c for text, _, _ in runs for c in text})
    if font_data is None:
        font_data = make_generic_font(chars)
    cmap = "\n".join(f"<{ord(c):04X}> <{ord(c):04X}>" for c in chars)
    mapping = f"/CIDInit /ProcSet findresource begin 12 dict begin begincmap /CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def /CMapName /Thai def /CMapType 2 def 1 begincodespacerange <0000> <FFFF> endcodespacerange {len(chars)} beginbfchar {cmap} endbfchar endcmap CMapName currentdict /CMap defineresource pop end end".encode()
    content = "\n".join(
        f"BT /F1 16 Tf 1 0 0 1 {x} {y} Tm <{text.encode('utf-16-be').hex()}> Tj ET"
        for text, x, y in runs
    ).encode()
    widths = " ".join(f"{ord(c)} [{0 if c in 'ัิีึืฺุู็่้๊๋์ํ๎' else 600}]" for c in chars)

    def stream(b):
        return f"<< /Length {len(b)} >>\nstream\n".encode() + b + b"\nendstream"

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 7 0 R >>",
        b"<< /Type /Font /Subtype /Type0 /BaseFont /Thai /Encoding /Identity-H /DescendantFonts [5 0 R] /ToUnicode 6 0 R >>",
        f"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /Thai /CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> /FontDescriptor 8 0 R /CIDToGIDMap /Identity /DW 600 /W [{widths}] >>".encode(),
        stream(mapping),
        stream(content),
        b"<< /Type /FontDescriptor /FontName /Thai /Flags 4 /FontBBox [0 -200 1000 1000] /ItalicAngle 0 /Ascent 800 /Descent -200 /CapHeight 700 /StemV 80 >>",
    ]
    if font_data is not None:
        objects[7] = objects[7].replace(b"/StemV 80", b"/StemV 80 /FontFile2 9 0 R")
        encoded = font_data.hex().encode() + b">"
        objects.append(
            f"<< /Length {len(encoded)} /Length1 {len(font_data)} /Filter /ASCIIHexDecode >>\nstream\n".encode()
            + encoded
            + b"\nendstream"
        )
        # Content CIDs are Unicode values; the font's GIDs are compact indices.
        font = TTFont(BytesIO(font_data))
        cmap = font.getBestCmap()
        cid_map = bytearray((max(map(ord, chars)) + 1) * 2)
        for c in chars:
            gid = font.getGlyphID(cmap[ord(c)])
            cid_map[ord(c) * 2 : ord(c) * 2 + 2] = gid.to_bytes(2, "big")
        compressed = zlib.compress(cid_map)
        objects[4] = objects[4].replace(b"/CIDToGIDMap /Identity", b"/CIDToGIDMap 10 0 R")
        objects.append(
            f"<< /Length {len(compressed)} /Filter /FlateDecode >>\nstream\n".encode()
            + compressed
            + b"\nendstream"
        )
    out = bytearray(b"%PDF-1.7\n")
    offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(out))
        out.extend(f"{i} 0 obj\n".encode() + obj + b"\nendobj\n")
    start = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode())
    out.extend(
        f"trailer << /Root 1 0 R /Size {len(objects) + 1} >>\nstartxref\n{start}\n%%EOF\n".encode()
    )
    path.write_bytes(out)
