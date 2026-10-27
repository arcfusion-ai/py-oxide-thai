//! Synthetic Type0 fonts with separately positioned Thai combining glyphs.
//! No external PDFs or font programs are needed for the Unicode/geometry tests.

use pdf_oxide::{converters::ConversionOptions, PdfDocument};
use std::collections::BTreeSet;

fn thai_pdf(runs: &[(&str, f32, f32)]) -> Vec<u8> {
    thai_pdf_with_font(runs, None)
}

fn thai_pdf_with_font(runs: &[(&str, f32, f32)], font: Option<&[u8]>) -> Vec<u8> {
    let chars: BTreeSet<char> = runs.iter().flat_map(|(s, _, _)| s.chars()).collect();
    let mappings: String = chars
        .iter()
        .map(|c| format!("<{:04X}> <{:04X}>\n", *c as u32, *c as u32))
        .collect();
    let cmap = format!(
        "/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n\
         /CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n\
         /CMapName /Thai def /CMapType 2 def\n\
         1 begincodespacerange <0000> <FFFF> endcodespacerange\n\
         {} beginbfchar\n{mappings}endbfchar\n\
         endcmap CMapName currentdict /CMap defineresource pop end end",
        chars.len()
    );
    let widths: String = chars
        .iter()
        .map(|c| {
            let width = if matches!(*c as u32, 0x0E31 | 0x0E34..=0x0E3A | 0x0E47..=0x0E4E) {
                0
            } else {
                600
            };
            format!("{} [{width}] ", *c as u32)
        })
        .collect();
    let content: String = runs
        .iter()
        .map(|(text, x, y)| {
            let hex: String = text.encode_utf16().map(|c| format!("{c:04X}")).collect();
            format!("BT /F1 16 Tf 1 0 0 1 {x} {y} Tm <{hex}> Tj ET\n")
        })
        .collect();
    let stream = |s: &str| format!("<< /Length {} >>\nstream\n{s}\nendstream", s.len());
    let mut objects = vec![
        "<< /Type /Catalog /Pages 2 0 R >>".to_string(),
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>".into(),
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 7 0 R >>".into(),
        "<< /Type /Font /Subtype /Type0 /BaseFont /Thai /Encoding /Identity-H /DescendantFonts [5 0 R] /ToUnicode 6 0 R >>".into(),
        format!("<< /Type /Font /Subtype /CIDFontType2 /BaseFont /Thai /CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> /FontDescriptor 8 0 R /CIDToGIDMap /Identity /DW 600 /W [{widths}] >>"),
        stream(&cmap),
        stream(&content),
        "<< /Type /FontDescriptor /FontName /Thai /Flags 4 /FontBBox [0 -200 1000 1000] /ItalicAngle 0 /Ascent 800 /Descent -200 /CapHeight 700 /StemV 80 >>".into(),
    ];
    if let Some(font) = font {
        objects[7] = objects[7].replace("/StemV 80", "/StemV 80 /FontFile2 9 0 R");
        let hex: String = font.iter().map(|b| format!("{b:02X}")).collect();
        objects.push(format!(
            "<< /Length {} /Length1 {} /Filter /ASCIIHexDecode >>\nstream\n{hex}>\nendstream",
            hex.len() + 1,
            font.len()
        ));
        let mut cid_map = vec![0u8; (0x0E34 + 1) * 2];
        for (cid, gid) in [(0x0E01, 1u16), (0x0E15, 2), (0x0E34, 3)] {
            cid_map[cid * 2..cid * 2 + 2].copy_from_slice(&gid.to_be_bytes());
        }
        let hex: String = cid_map.iter().map(|b| format!("{b:02X}")).collect();
        objects[4] = objects[4].replace("/CIDToGIDMap /Identity", "/CIDToGIDMap 10 0 R");
        objects.push(format!(
            "<< /Length {} /Filter /ASCIIHexDecode >>\nstream\n{hex}>\nendstream",
            hex.len() + 1
        ));
    }
    let mut pdf = b"%PDF-1.7\n".to_vec();
    let mut offsets = Vec::new();
    for (i, object) in objects.iter().enumerate() {
        offsets.push(pdf.len());
        pdf.extend_from_slice(format!("{} 0 obj\n{object}\nendobj\n", i + 1).as_bytes());
    }
    let xref = pdf.len();
    pdf.extend_from_slice(
        format!("xref\n0 {}\n0000000000 65535 f \n", objects.len() + 1).as_bytes(),
    );
    for offset in offsets {
        pdf.extend_from_slice(format!("{offset:010} 00000 n \n").as_bytes());
    }
    pdf.extend_from_slice(
        format!(
            "trailer << /Root 1 0 R /Size {} >>\nstartxref\n{xref}\n%%EOF\n",
            objects.len() + 1
        )
        .as_bytes(),
    );
    pdf
}

fn assert_text_surfaces(runs: &[(&str, f32, f32)], expected: &str) {
    let doc = PdfDocument::from_bytes(thai_pdf(runs)).unwrap();
    let options = ConversionOptions::default();
    for text in [
        doc.extract_text(0).unwrap(),
        doc.to_plain_text(0, &options).unwrap(),
        doc.to_markdown(0, &options).unwrap(),
        doc.to_html(0, &options).unwrap(),
    ] {
        assert!(text.contains(expected), "expected {expected:?} in {text:?}");
    }
    let lines = doc.extract_text_lines(0).unwrap();
    assert!(lines.iter().any(|l| l.text.contains(expected)), "lines: {lines:?}");
    let words = doc.extract_words(0).unwrap();
    for word in expected.split_whitespace() {
        assert!(words.iter().any(|w| w.text.contains(word)), "missing word {word:?}");
    }
}

#[test]
fn test_thai_raised_vowel_and_tone_keep_logical_order() {
    assert_text_surfaces(
        &[
            ("ก", 72., 720.),
            ("ิ", 73., 723.),
            ("่", 72., 726.),
            ("ติ", 81.6, 720.),
        ],
        "กิ่ติ",
    );
}

#[test]
fn test_thai_left_shifted_marks_follow_their_base() {
    assert_text_surfaces(
        &[
            ("ก", 72., 720.),
            ("ิ", 70., 720.),
            ("่", 69., 720.),
            ("ติ", 81.6, 720.),
        ],
        "กิ่ติ",
    );
}

#[test]
fn test_thai_lower_vowel_stays_in_name() {
    assert_text_surfaces(&[("ศ", 72., 720.), ("ุ", 72., 716.), ("ภ", 81.6, 720.)], "ศุภ");
}

#[test]
fn test_thai_nikhahit_keeps_decomposed_sara_am() {
    assert_text_surfaces(
        &[
            ("น", 72., 720.),
            ("้", 72., 724.),
            ("ํ", 72., 727.),
            ("า", 81.6, 720.),
        ],
        "น้ํา",
    );
}

#[test]
fn test_thai_mark_inside_a_multi_character_run() {
    assert_text_surfaces(&[("กต", 72., 720.), ("ิ", 72., 724.), ("่", 72., 727.)], "กิ่ต");
}

#[test]
fn test_thai_inline_and_explicit_spaces_are_preserved() {
    assert_text_surfaces(&[("กิ่ติ ศุภ", 72., 720.)], "กิ่ติ ศุภ");
}

#[test]
fn test_thai_mark_does_not_cross_a_line_or_column() {
    let doc =
        PdfDocument::from_bytes(thai_pdf(&[("ก", 72., 720.), ("ิ", 72., 740.), ("่", 200., 724.)]))
            .unwrap();
    let text = doc.extract_text(0).unwrap();
    assert!(!text.contains("กิ") && !text.contains("ก่"), "unrelated marks attached: {text:?}");
    assert!(text.contains('ิ') && text.contains('่'), "unattached marks must remain visible");
}

#[test]
fn test_thai_negative_side_bearing_attaches_ink_to_previous_consonant() {
    use base64::Engine;
    // Original rectangular glyphs, generated by tools/thai_fixtures.py::make_mark_font.
    // The vowel origin coincides with ต, but its ink lies over ก.
    let font = base64::engine::general_purpose::STANDARD.decode(
        "AAEAAAAKAIAAAwAgT1MvMlLgUygAAAEoAAAAYGNtYXAOKRyfAAABmAAAAERnbHlmitdyVgAAAegAAABKaGVhZFiNpQAAAACsAAAANmhoZWEETgGVAAAA5AAAACRobXR4Bwj+1AAAAYgAAAAQbG9jYQAxABgAAAHcAAAACm1heHAABgAGAAABCAAAACBuYW1lD8gMSgAAAjQAAABycG9zdEFSRE8AAAKoAAAAOQABAAAAAQAAY2rrBF8PPPUAAwPoAAAAAHwlsIAAAAAAfCWwgP7UAAACWAMgAAAAAwACAAAAAAAAAAEAAAMg/zgAAAJY/tQAAAJYAAEAAAAAAAAAAAAAAAAAAAAEAAEAAAAEAAQAAQAAAAAAAgAAAAAAAAAAAAAAAAAAAAAAAwJYAZAABQAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAPz8/PwAADgEONAMg/zgAAAMgAMgAAAAAAAAAAAAAAAAAAAAgAAACWAAAAlgAAAJYAAAAAP7UAAAAAgAAAAMAAAAUAAMAAQAAABQABAAwAAAACAAIAAIAAA4BDhUONP//AAAOAQ4VDjT///IA8e3xzwABAAAAAAAAAAAAAAAAAAwAGAAlAAAAAQAAAAACWAK8AAMAADEhESECWP2oArwAAQAAAAACWAK8AAMAADEhESECWP2oArwAAf7UArz/nAMgAAMAAAEzNSP+1MjIArxkAAAAAAAABAA2AAEAAAAAAAEADQAAAAEAAAAAAAIABwANAAMAAQQJAAEAGgAUAAMAAQQJAAIADgAuU3ludGhldGljTWFya1JlZ3VsYXIAUwB5AG4AdABoAGUAdABpAGMATQBhAHIAawBSAGUAZwB1AGwAYQByAAAAAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAAABAgEDAQQEYmFzZQRuZXh0BG1hcmsAAAA="
    ).unwrap();
    let doc = PdfDocument::from_bytes(thai_pdf_with_font(
        &[("กต", 72., 720.), ("ิ", 81.6, 724.)],
        Some(&font),
    ))
    .unwrap();
    let text = doc.extract_text(0).unwrap();
    assert!(text.contains("กิต"), "mark followed its origin rather than its ink: {text:?}");
    assert!(!text.contains("กติ"));
}
