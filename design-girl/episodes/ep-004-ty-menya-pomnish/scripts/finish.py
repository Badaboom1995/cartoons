#!/usr/bin/env python3
"""Finishes EP4: rendered picture + the "One Eternity Later" card over shot 27 + the mixed audio = renders/ep-004.mp4.

    python3 finish.py <picture.mp4>          a video from scripts/render.py, starting at timeline frame 1

The card (overlays/card_one_eternity_later.png, not 9:16) is fitted to the width over a blurred, enlarged copy of
itself, so no letter of "Eternity" is cut. The audio is cut to the picture's length.
"""
import json
import subprocess
import sys
from pathlib import Path

EP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EP / "scripts"))
FPS, W, H = 24, 1080, 1920
CARD = EP / "overlays" / "card_one_eternity_later.png"
CARD_SHOT = 27


def fail(message):
    sys.exit(f"finish: {message}")


def frames_of(path):
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries",
                            "stream=nb_read_frames,r_frame_rate,width,height", "-of", "json", str(path)],
                           capture_output=True, text=True, check=True)
    s = json.loads(probe.stdout)["streams"][0]
    num, den = s["r_frame_rate"].split("/")
    if int(num) != FPS * int(den) or (s["width"], s["height"]) != (W, H):
        fail(f"{path} is {s['r_frame_rate']} fps {s['width']}x{s['height']}, expected {FPS} fps {W}x{H}")
    return int(s["nb_read_frames"])


def main():
    if len(sys.argv) != 2:
        fail("usage: finish.py <picture.mp4>")
    picture = Path(sys.argv[1])
    audio = EP / "renders" / "ep-004-audio.wav"
    output = EP / "renders" / "ep-004.mp4"
    for p in (picture, audio, CARD):
        if not p.exists():
            fail(f"{p} does not exist")
    timeline = json.loads((EP / "timeline.json").read_text(encoding="utf-8"))
    count = frames_of(picture)
    expected = timeline["frame_end"] - timeline["frame_start"] + 1
    if count != expected:
        fail(f"the picture has {count} frames, the timeline {expected}")
    card = next(s for s in timeline["shots"] if s["id"] == CARD_SHOT)
    a, z = card["first_frame"] - timeline["frame_start"], card["last_frame"] - timeline["frame_start"]
    steps = [
        f"[2:v]split[c1][c2]",
        f"[c1]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=30:2[bg]",
        f"[c2]scale={W}:-2[fg]",
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2,format=rgb24[card]",
        f"[0:v][card]overlay=enable='between(n,{a},{z})':format=rgb,"
        "scale=out_color_matrix=bt709:out_range=tv:flags=accurate_rnd+full_chroma_int,format=yuv420p,setsar=1[video]",
        f"[1:a]apad,atrim=end={count / FPS:.6f},asetpts=PTS-STARTPTS[sound]",
    ]
    command = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(picture), "-i", str(audio),
               "-loop", "1", "-framerate", str(FPS), "-i", str(CARD),
               "-filter_complex", ";".join(steps), "-map", "[video]", "-map", "[sound]",
               "-frames:v", str(count), "-r", str(FPS),
               "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-profile:v", "high", "-pix_fmt", "yuv420p",
               "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
               "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart", str(output)]
    subprocess.run(command, check=True)
    print(f"finish: wrote {output} ({count} frames, card on {a + 1}-{z + 1})")


if __name__ == "__main__":
    main()
