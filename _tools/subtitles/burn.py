#!/usr/bin/env python3
"""Burns subtitles from an episode's timeline.json into its final video.

    python3 _tools/subtitles/burn.py <episode-dir>

Reads renders/<id>.mp4 and writes renders/<id>-sub.mp4. The source video and its audio stay untouched.
"""
import json
import math
import re
import subprocess
import sys
import tempfile
from pathlib import Path

WIDTH, HEIGHT = 1080, 1920
FONT = "Helvetica Neue"
FONT_SIZE = 62
OUTLINE = 2.5
SPACING = 1.5
HALO = 13                    # soft dark glow that keeps white text readable on light backgrounds
HALO_BLUR = 11
MARGIN_X = 90
MARGIN_BOTTOM = 340          # stays above the Reels caption and buttons
MAX_LINE = 27                # characters on one subtitle row
HOLD_FRAMES = 6              # a line stays a little after the voice ends


def balanced_rows(text):
    """One row when it fits, otherwise two rows of similar length, preferring a break after punctuation."""
    if len(text) <= MAX_LINE:
        return text
    words = text.split()
    options = []
    for i in range(1, len(words)):
        first, second = " ".join(words[:i]), " ".join(words[i:])
        penalty = max(len(first), len(second))
        if max(len(first), len(second)) > MAX_LINE:
            penalty += 100
        if first[-1] in ".,!?:":
            penalty -= 6
        if len(words[i - 1]) <= 2:   # do not leave a short preposition hanging at the end of a row
            penalty += 6
        options.append((penalty, first, second))
    _, first, second = min(options, key=lambda option: option[0])
    return f"{first}\\N{second}"


def cards(text):
    """Splits a line that does not fit in two rows into consecutive cards, at sentences and then at commas."""
    if len(text) <= MAX_LINE * 2 - 4:
        return [text]
    result = []
    for sentence in re.findall(r"[^.!?]+[.!?]*", text):
        sentence = sentence.strip()
        if len(sentence) <= MAX_LINE * 2 - 4:
            result.append(sentence)
            continue
        current = ""
        for part in re.findall(r"[^,]+,?", sentence):
            part = part.strip()
            joined = f"{current} {part}".strip()
            if current and len(joined) > MAX_LINE * 2 - 4:
                result.append(current)
                current = part
            else:
                current = joined
        result.append(current)
    return result


def stamp(frame, fps):
    """ASS time of the moment frame (1-based) appears, rounded down to centiseconds so that frame is included."""
    total = math.floor((frame - 1) / fps * 100 + 1e-6)
    hours, rest = divmod(total, 360000)
    minutes, rest = divmod(rest, 6000)
    seconds, centis = divmod(rest, 100)
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centis:02d}"


def events(timeline):
    fps = timeline["fps"]
    shots = timeline["shots"]
    lines = [line for shot in shots for line in shot["lines"]]
    rows = []
    for index, line in enumerate(lines):
        start, end = line["first_frame"], line["last_frame"]
        shot_end = next((s["last_frame"] for s in shots if s["first_frame"] <= end <= s["last_frame"]), end)
        limit = lines[index + 1]["first_frame"] - 1 if index + 1 < len(lines) else timeline["frame_end"]
        end = max(end, min(end + HOLD_FRAMES, shot_end, limit))

        parts = cards(line["text"])
        weight = sum(len(part) for part in parts)
        cursor = start
        for number, part in enumerate(parts):
            last = end if number == len(parts) - 1 else cursor + round((end - start + 1) * len(part) / weight) - 1
            times = f"{stamp(cursor, fps)},{stamp(last + 1, fps)}"
            text = balanced_rows(part)
            rows.append(f"Dialogue: 0,{times},Halo,,0,0,0,,{{\\blur{HALO_BLUR}}}{text}")
            rows.append(f"Dialogue: 1,{times},Sub,,0,0,0,,{text}")
            cursor = last + 1
    return rows


def ass_document(timeline):
    layout = f"2,{MARGIN_X},{MARGIN_X},{MARGIN_BOTTOM},1"
    style = (f"Style: Sub,{FONT},{FONT_SIZE},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,"
             f"-1,0,0,0,100,100,{SPACING},0,1,{OUTLINE},0,{layout}")
    halo = (f"Style: Halo,{FONT},{FONT_SIZE},&H30000000,&H30000000,&H50000000,&H00000000,"
            f"-1,0,0,0,100,100,{SPACING},0,1,{HALO},0,{layout}")
    return "\n".join([
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {WIDTH}", f"PlayResY: {HEIGHT}",
        "WrapStyle: 2", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        halo, style, "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        *events(timeline), "",
    ])


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    episode = Path(sys.argv[1]).resolve()
    timeline = json.loads((episode / "timeline.json").read_text(encoding="utf-8"))
    source = episode / "renders" / f"{timeline['id']}.mp4"
    output = episode / "renders" / f"{timeline['id']}-sub.mp4"
    if not source.exists():
        sys.exit(f"burn: {source} does not exist")

    with tempfile.TemporaryDirectory() as folder:
        (Path(folder) / "subs.ass").write_text(ass_document(timeline), encoding="utf-8")
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(source), "-vf", "ass=subs.ass",
                        "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-profile:v", "high",
                        "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", str(output)],
                       cwd=folder, check=True)
    print(f"burn: wrote {output}")


if __name__ == "__main__":
    main()
