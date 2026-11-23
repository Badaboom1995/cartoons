#!/usr/bin/env python3
"""Finishes EP3: rendered picture + captions from timeline.json + mixed audio = renders/ep-003.mp4.

    python3 finish.py                                    frames from renders/ep-003_####.png
    python3 finish.py some/video.mp4                     a video that starts at timeline frame 1
    python3 finish.py part.mp4 --first-frame 200         a video that starts at timeline frame 200

A numbered sequence takes its first frame from the file names. Audio is cut to match the picture.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

EP = Path(__file__).resolve().parents[1]
FPS = 24
CAPTIONS = {"Тем же вечером": "caption-evening.png"}
CAPTION_FRAMES = 26                  # about 1.1 s
FADE_IN, FADE_OUT = 4, 6


def fail(message):
    sys.exit(f"finish: {message}")


def sequence_input(pattern):
    head, tail = pattern.name.split("####")
    names = re.compile(re.escape(head) + r"(\d{4})" + re.escape(tail))
    frames = sorted(int(m.group(1)) for m in map(names.fullmatch, (p.name for p in pattern.parent.glob("*"))) if m)
    if not frames:
        fail(f"no frames match {pattern}")
    missing = sorted(set(range(frames[0], frames[-1] + 1)) - set(frames))
    if missing:
        fail(f"{len(missing)} frames are missing, the first is {missing[0]}")
    numbered = str(pattern.parent / f"{head}%04d{tail}").replace("%", "%%").replace("%%04d", "%04d")
    return frames[0], len(frames), ["-framerate", str(FPS), "-start_number", str(frames[0]), "-i", numbered]


def video_input(path, first_frame):
    if not path.exists():
        fail(f"{path} does not exist")
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries",
                            "stream=nb_read_frames,r_frame_rate", "-of", "json", str(path)],
                           capture_output=True, text=True, check=True)
    stream = json.loads(probe.stdout)["streams"][0]
    num, den = stream["r_frame_rate"].split("/")
    if int(num) != FPS * int(den):
        fail(f"{path} is {stream['r_frame_rate']} fps, expected {FPS}")
    return first_frame, int(stream["nb_read_frames"]), ["-i", str(path)]


def caption_layers(timeline, first, count, next_input):
    """Extra ffmpeg inputs and filter steps that lay each shot's caption over the picture."""
    inputs, steps, label = [], ["[0:v]setpts=PTS-STARTPTS[base]"], "base"
    for shot in timeline["shots"]:
        text = shot.get("caption")
        if not text:
            continue
        if text not in CAPTIONS:
            fail(f"shot {shot['id']}: no image for the caption «{text}»")
        image = EP / "overlays" / CAPTIONS[text]
        if not image.exists():
            fail(f"{image} is missing, run make_screens.py first")
        start = shot["first_frame"]
        length = min(CAPTION_FRAMES, shot["last_frame"] - start + 1)
        skip = max(0, first - start)
        if skip >= length or start >= first + count:
            continue
        offset = max(0, start - first)
        index = next_input + len(inputs) // 8
        # ffmpeg's fade is fully transparent on its first frame, so one lead-in frame is faded and then dropped
        inputs += ["-loop", "1", "-framerate", str(FPS), "-t", f"{(length + 2) / FPS:.6f}", "-i", str(image)]
        steps.append(f"[{index}:v]format=rgba,fade=t=in:s=0:n={FADE_IN}:alpha=1,"
                     f"fade=t=out:s={length + 1 - FADE_OUT}:n={FADE_OUT}:alpha=1,"
                     f"trim=start_frame={skip + 1}:end_frame={length + 1},"
                     f"setpts=PTS-STARTPTS+{offset}/({FPS}*TB)[cap{index}]")
        steps.append(f"[{label}][cap{index}]overlay=eof_action=pass:format=rgb[over{index}]")
        label = f"over{index}"
    steps.append(f"[{label}]scale=out_color_matrix=bt709:out_range=tv:flags=accurate_rnd+full_chroma_int,"
                 "format=yuv420p,setsar=1[video]")
    return inputs, steps


def main():
    parser = argparse.ArgumentParser(description="Adds captions and audio to the rendered EP3 picture.")
    parser.add_argument("input", nargs="?", type=Path, default=EP / "renders" / "ep-003_####.png",
                        help="a video, or a frame pattern with ####")
    parser.add_argument("--first-frame", type=int, default=1, help="timeline frame of a video's first frame")
    parser.add_argument("--audio", type=Path, default=EP / "renders" / "ep-003-audio.wav")
    parser.add_argument("--output", type=Path, default=EP / "renders" / "ep-003.mp4")
    args = parser.parse_args()

    if not args.audio.exists():
        fail(f"{args.audio} does not exist")
    if args.output.resolve() == args.input.resolve():
        fail("the output would overwrite the input")
    if "####" in args.input.name:
        first, count, picture = sequence_input(args.input)
    else:
        first, count, picture = video_input(args.input, args.first_frame)

    timeline = json.loads((EP / "timeline.json").read_text(encoding="utf-8"))
    duration = count / FPS
    sound = ["-ss", f"{(first - timeline['frame_start']) / FPS:.6f}", "-i", str(args.audio)]
    layers, steps = caption_layers(timeline, first, count, next_input=2)
    steps.append(f"[1:a]apad,atrim=end={duration:.6f},asetpts=PTS-STARTPTS[sound]")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    command = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *picture, *sound, *layers,
               "-filter_complex", ";".join(steps), "-map", "[video]", "-map", "[sound]",
               "-frames:v", str(count), "-r", str(FPS),
               "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-profile:v", "high", "-pix_fmt", "yuv420p",
               "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
               "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
               "-movflags", "+faststart", str(args.output)]
    subprocess.run(command, check=True)
    print(f"finish: wrote {args.output} ({count} frames from timeline frame {first})")


if __name__ == "__main__":
    main()
