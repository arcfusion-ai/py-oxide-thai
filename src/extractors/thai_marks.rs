//! Attach independently positioned Thai marks before geometric reading-order sorting.

use crate::fonts::FontInfo;
use crate::layout::TextSpan;
use std::{collections::HashMap, sync::Arc};

fn is_mark(c: char) -> bool {
    matches!(c as u32, 0x0E31 | 0x0E34..=0x0E3A | 0x0E47..=0x0E4E)
}

/// Keep a positioned vowel/tone with its consonant. Only mark-only runs are
/// moved; already mapped strings, explicit spaces, and non-Thai scripts stay intact.
pub(super) fn attach_positioned_marks(
    spans: &mut Vec<TextSpan>,
    fonts: &HashMap<String, Arc<FontInfo>>,
) {
    let marks: Vec<usize> = spans
        .iter()
        .enumerate()
        .filter(|(_, s)| {
            !s.text.is_empty()
                && s.text.chars().all(is_mark)
                && s.wmode == 0
                && s.rotation_degrees == 0.0
                && !s.mirrored
                && s.font_size.is_finite()
                && s.font_size > 0.0
                && s.bbox.x.is_finite()
                && s.bbox.y.is_finite()
        })
        .map(|(i, _)| i)
        .collect();
    if marks.is_empty() {
        return;
    }

    let faces: HashMap<&str, ttf_parser::Face<'_>> = fonts
        .iter()
        .filter_map(|(name, font)| {
            let data = font.embedded_font_data.as_ref()?;
            Some((name.as_str(), ttf_parser::Face::parse(data, 0).ok()?))
        })
        .collect();
    let ink_center = |span: &TextSpan, c: char| -> Option<f32> {
        let face = faces.get(span.font_name.as_str())?;
        let bounds = face.glyph_bounding_box(face.glyph_index(c)?)?;
        let units = face.units_per_em() as f32;
        Some(
            (bounds.x_min as f32 + bounds.x_max as f32) * 0.5 / units
                * span.font_size
                * span.horizontal_scaling
                / 100.0,
        )
    };

    // Index consonant origins once. Most pages have no detached marks and
    // never reach this allocation; a marked page searches only nearby glyphs.
    let mut bases = Vec::new();
    for (i, span) in spans.iter().enumerate() {
        if span.wmode != 0
            || span.rotation_degrees != 0.0
            || span.mirrored
            || !span.bbox.y.is_finite()
        {
            continue;
        }
        for (j, glyph) in span.to_chars().iter().enumerate() {
            if matches!(glyph.char as u32, 0x0E01..=0x0E2E) && glyph.origin_x.is_finite() {
                bases.push((glyph.origin_x, i, j, ink_center(span, glyph.char)));
            }
        }
    }
    bases.sort_by(|a, b| a.0.total_cmp(&b.0));
    let mut attachments: Vec<Vec<(usize, usize)>> = vec![Vec::new(); spans.len()];
    let mut removed = vec![false; spans.len()];
    for i in marks {
        let mark = &spans[i];
        let slack = mark.font_size * 0.35;
        let mark_center = mark.text.chars().next().and_then(|c| ink_center(mark, c));
        let lo = bases.partition_point(|b| b.0 < mark.bbox.x - mark.font_size);
        let hi = bases.partition_point(|b| b.0 <= mark.bbox.x + mark.font_size);
        let mut best: Option<(f32, usize, usize)> = None;
        for &(x, j, glyph_index, base_center) in &bases[lo..hi] {
            let base = &spans[j];
            // A mark cannot cross font, structure, artifact, or paint scopes.
            // The half-em vertical window excludes adjacent body-text lines.
            if base.font_name != mark.font_name
                || (base.font_size - mark.font_size).abs() > mark.font_size * 0.05
                || base.mcid != mark.mcid
                || base.mcid_scope != mark.mcid_scope
                || base.artifact_type != mark.artifact_type
                || base.color != mark.color
                || (base.bbox.y - mark.bbox.y).abs() > mark.font_size * 0.55
            {
                continue;
            }
            // Nonspacing glyphs can have a negative left side bearing: their
            // origin sits at the NEXT consonant while their ink is over the
            // previous one. Use actual font bounds when both are available.
            let dx = match (mark_center, base_center) {
                (Some(m), Some(b)) => (x + b - mark.bbox.x - m).abs(),
                _ => (x - mark.bbox.x).abs(),
            };
            if dx > slack {
                continue;
            }
            let score = dx + (base.bbox.y - mark.bbox.y).abs() * 0.2;
            if best.is_none_or(|(s, _, _)| score < s) {
                best = Some((score, j, glyph_index));
            }
        }
        if let Some((_, j, glyph_index)) = best {
            let chars: Vec<char> = spans[j].text.chars().collect();
            let mut after = glyph_index + 1;
            while after < chars.len() && is_mark(chars[after]) {
                after += 1;
            }
            attachments[j].push((after, i));
            removed[i] = true;
        }
    }

    for j in 0..spans.len() {
        if attachments[j].is_empty() {
            continue;
        }
        // Preserve the PDF's logical mark order, rather than sorting marks by
        // their visual x/y positions or guessing a spelling from a dictionary.
        attachments[j].sort_by_key(|&(after, i)| (after, spans[i].sequence));
        let glyphs = spans[j].to_chars();
        let mut text = String::new();
        let mut widths = Vec::new();
        let mut origins = Vec::new();
        for (k, glyph) in glyphs.iter().enumerate() {
            text.push(glyph.char);
            widths.push(glyph.advance_width);
            origins.push(glyph.origin_x);
            for &(_, i) in attachments[j].iter().filter(|&&(after, _)| after == k + 1) {
                for mark in spans[i].to_chars() {
                    text.push(mark.char);
                    // A separately positioned mark does not advance the body run.
                    widths.push(0.0);
                    origins.push(mark.origin_x);
                }
            }
        }
        spans[j].text = text;
        spans[j].char_widths = widths;
        spans[j].char_x_offsets = origins;
    }
    let mut i = 0;
    spans.retain(|_| {
        let keep = !removed[i];
        i += 1;
        keep
    });
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::geometry::Rect;

    fn pair() -> Vec<TextSpan> {
        vec![
            TextSpan {
                text: "ก".into(),
                bbox: Rect::new(72., 720., 9.6, 16.),
                font_size: 16.,
                ..Default::default()
            },
            TextSpan {
                text: "ิ".into(),
                bbox: Rect::new(72., 724., 0., 16.),
                font_size: 16.,
                sequence: 1,
                ..Default::default()
            },
        ]
    }

    #[test]
    fn test_thai_attachment_does_not_cross_structure_or_font_scopes() {
        for scope in 0..5 {
            let mut spans = pair();
            match scope {
                0 => spans[1].mcid = Some(3),
                1 => spans[1].font_name = "Other".into(),
                2 => spans[1].mcid_scope = Some(crate::structure::McidScope::Page(1)),
                3 => spans[1].artifact_type = Some(crate::extractors::text::ArtifactType::Layout),
                _ => spans[1].color.r = 1.,
            }
            attach_positioned_marks(&mut spans, &HashMap::new());
            assert_eq!(spans.len(), 2, "crossed scope {scope}");
        }
    }

    #[test]
    fn test_thai_attachment_preserves_every_nonspacing_mark() {
        for mark in [
            'ั', 'ิ', 'ี', 'ึ', 'ื', 'ุ', 'ู', 'ฺ', '็', '่', '้', '๊', '๋', '์', 'ํ', '๎',
        ] {
            let mut spans = pair();
            spans[1].text = mark.to_string();
            attach_positioned_marks(&mut spans, &HashMap::new());
            assert_eq!(spans.len(), 1);
            assert_eq!(spans[0].text, format!("ก{mark}"));
            assert_eq!(spans[0].char_widths.len(), 2);
            assert_eq!(spans[0].char_x_offsets, vec![72., 72.]);
        }
    }

    #[test]
    fn test_thai_attachment_leaves_rotated_and_vertical_runs_untouched() {
        for vertical in [false, true] {
            let mut spans = pair();
            if vertical {
                spans[1].wmode = 1;
            } else {
                spans[1].rotation_degrees = 90.;
            }
            attach_positioned_marks(&mut spans, &HashMap::new());
            assert_eq!(spans.len(), 2);
        }
    }
}
