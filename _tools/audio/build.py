#!/usr/bin/env python3
"""Audio version of an episode from its episode.json: voices, one mixed track, one player page.

    python3 _tools/audio/build.py <episode-dir>              # voice missing lines, build the page
    python3 _tools/audio/build.py <episode-dir> --force v17  # re-voice the lines v17...
    python3 _tools/audio/build.py <episode-dir> --no-voices  # only rebuild from existing audio

Audio is matched by line id in <episode>/audio/voice: v07.wav or v07_anything.wav (wav, mp3, m4a, aiff, flac).
Voices come from <character>/voices.json, and the episode's own "voices" add to or override them.
Output: <episode>/renders/<id>-audio.wav and <id>-preview.html (a single file with the audio inside).
The Replicate key is REPLICATE_API_TOKEN from the environment or .env.local in the repository root.
"""
import argparse
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import wave
from array import array
from pathlib import Path

TOOL = Path(__file__).resolve().parent
REPO = TOOL.parents[1]
MODEL_URL = "https://api.replicate.com/v1/models/google/gemini-3.8-flash-tts/predictions"
USER_AGENT = "voice-builder/1.0"
RATE = 24000
AUDIO_TYPES = {".wav", ".mp3", ".m4a", ".aiff", ".flac"}
# Defaults of the episode's optional "pacing" block. A line can set its own "tempo".
PACING = {
    "start": 0.4,       # silence before the first shot
    "line_gap": 0.25,   # between two lines inside one shot
    "tail": 0.25,       # after the last line of a shot
    "end": 0.6,         # after the last shot
    "tempo": 1.0,       # speech speed, pitch and timbre preserved
    "max_pause": 0,     # pauses inside a line are cut down to this many seconds, 0 keeps them
}
TRIM = ("silenceremove=start_periods=1:start_silence=0.05:start_threshold=-50dB,areverse,"
        "silenceremove=start_periods=1:start_silence=0.08:start_threshold=-50dB,areverse")


def load_config(ep):
    path = ep / "episode.json"
    if not path.exists():
        sys.exit(f"no episode.json in {ep}")
    cfg = json.loads(path.read_text(encoding="utf-8"))
    shared = ep.parents[1] / "voices.json"
    voices = json.loads(shared.read_text(encoding="utf-8")) if shared.exists() else {}
    voices.update(cfg.get("voices", {}))
    cfg["voices"] = voices
    seen = set()
    for line in all_lines(cfg):
        if line["id"] in seen:
            sys.exit(f"duplicate line id {line['id']}")
        seen.add(line["id"])
        if line["who"] not in voices:
            sys.exit(f"{line['id']}: no voice for '{line['who']}'")
    return cfg


def require_approved_script(ep):
    """An episode that keeps a status.md is voiced only after step 1 is ticked there."""
    status = ep / "status.md"
    if status.exists() and not re.search(r"^- \[[xXхХ]\] 1\.", status.read_text(encoding="utf-8"), re.MULTILINE):
        sys.exit(f"the script is not approved: step 1 is not ticked in {status}")


def all_lines(cfg):
    return [l for scene in cfg["scenes"] for shot in scene["shots"] for l in shot.get("lines", [])]


def find_audio(ep, line_id):
    found = sorted(p for p in (ep / "audio" / "voice").glob(f"{line_id}*")
                   if p.suffix.lower() in AUDIO_TYPES and (p.stem == line_id or p.stem.startswith(line_id + "_")))
    if len(found) > 1:
        sys.exit(f"{line_id}: several audio files: {[p.name for p in found]}")
    return found[0] if found else None


def api_token():
    token = os.environ.get("REPLICATE_API_TOKEN")
    env = REPO / ".env.local"
    if not token and env.exists():
        for row in env.read_text().splitlines():
            if row.strip().startswith("REPLICATE_API_TOKEN="):
                token = row.split("=", 1)[1].strip().strip("\"'")
    if not token:
        sys.exit("REPLICATE_API_TOKEN not found: add it to .env.local in the repository root")
    return token


def call(url, token, body=None, wait=False):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": USER_AGENT}
    if wait:
        headers["Prefer"] = "wait=60"
    data = json.dumps(body).encode() if body is not None else None
    for attempt in range(12):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers), timeout=120) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            if e.code not in (429, 500, 502, 503, 504) or attempt == 11:
                sys.exit(f"Replicate error {e.code}: {detail[:400]}")
            try:
                delay = float(json.loads(detail).get("retry_after", 5))
            except (ValueError, AttributeError):
                delay = 5
            time.sleep(delay + 1)
        except urllib.error.URLError:
            if attempt == 11:
                raise
            time.sleep(5)


def synth(line, voice, token):
    style = voice.get("style", "") + (f" Подача: {line['how']}." if line.get("how") else "")
    body = {"input": {"text": line["text"], "style": style.strip(), "voice": voice["voice"], "output_format": "wav"}}
    p = call(MODEL_URL, token, body, wait=True)
    deadline = time.time() + 240
    while p["status"] not in ("succeeded", "failed", "canceled"):
        if time.time() > deadline:
            sys.exit(f"{line['id']}: timed out")
        time.sleep(2)
        p = call(p["urls"]["get"], token)
    if p["status"] != "succeeded":
        sys.exit(f"{line['id']}: {p['status']}: {p.get('error')}")
    url = p["output"][0] if isinstance(p["output"], list) else p["output"]
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=120) as r:
        return r.read()


def save_voice(raw, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
        tmp.write(raw)
        tmp.flush()
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", tmp.name, "-af", TRIM, "-ar", str(RATE), "-ac", "1",
                        "-c:a", "pcm_s16le", str(path)], check=True)


def make_voices(ep, cfg, force):
    todo = [l for l in all_lines(cfg) if not find_audio(ep, l["id"]) or any(l["id"].startswith(f) for f in force)]
    if not todo:
        return
    token = api_token()
    for n, line in enumerate(todo, 1):
        path = find_audio(ep, line["id"]) or ep / "audio" / "voice" / f"{line['id']}_{line['who']}.wav"
        save_voice(synth(line, cfg["voices"][line["who"]], token), path.with_suffix(".wav"))
        print(f"voiced {n}/{len(todo)}: {path.with_suffix('.wav').name}", flush=True)


def decode(path):
    return subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", str(RATE), "-"],
                          check=True, capture_output=True).stdout


def paced_audio(ep, line, pace):
    """The take as it plays in the episode. Takes in audio/voice stay as voiced; changed copies go to audio/paced."""
    source = find_audio(ep, line["id"])
    tempo = line.get("tempo", pace["tempo"])
    filters = []
    if pace["max_pause"]:
        filters.append(f"silenceremove=stop_periods=-1:stop_duration={pace['max_pause']}:stop_threshold=-40dB")
    if tempo != 1:
        filters.append(f"rubberband=tempo={tempo}:formant=preserved:pitchq=quality")
    if not filters:
        return source
    out = ep / "audio" / "paced" / f"{line['id']}.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(source), "-af", ",".join(filters), "-ar", str(RATE),
                    "-ac", "1", "-c:a", "pcm_s16le", str(out)], check=True)
    return out


def build_timeline(ep, cfg):
    """Shots follow each other; a shot lasts its planned duration or as long as its lines need."""
    pace = {**PACING, **cfg.get("pacing", {})}
    pcm, shots, t = {}, [], pace["start"]
    for s_index, scene in enumerate(cfg["scenes"]):
        for shot in scene["shots"]:
            start, cursor, lines = t, t + shot.get("lead", 0), []
            for line in shot.get("lines", []):
                if not find_audio(ep, line["id"]):
                    sys.exit(f"{line['id']}: no audio file")
                path = paced_audio(ep, line, pace)
                pcm[line["id"]] = decode(path)
                end = cursor + len(pcm[line["id"]]) / 2 / RATE
                lines.append({"id": line["id"], "who": line["who"], "text": line["text"], "how": line.get("how", ""),
                              "file": path.relative_to(ep).as_posix(),
                              "start": round(cursor, 3), "end": round(end, 3)})
                cursor = end + line.get("gap_after", pace["line_gap"])
            needed = cursor - pace["line_gap"] + pace["tail"] - start if lines else 0
            t = start + max(shot.get("duration", 0), needed) - shot.get("cut_early", 0)  # the next shot starts under the last words
            sfx = []
            for fx in shot.get("sfx", []):  # {"id", "file" relative to the episode, "at" seconds into the shot, optional "gain"}
                pcm[fx["id"]] = decode(ep / fx["file"])
                sfx.append({"id": fx["id"], "file": fx["file"], "gain": fx.get("gain", 1.0), "start": round(start + fx["at"], 3)})
            shots.append({"id": shot["id"], "scene": s_index, "framing": shot.get("framing", ""),
                          "camera": shot.get("camera", ""), "action": shot.get("action", ""),
                          "why": shot.get("why", ""),
                          "sound": shot.get("sound", ""), "caption": shot.get("caption", ""),
                          "transition": shot.get("transition"), "sfx": sfx,
                          "start": round(start, 3), "end": round(t, 3), "lines": lines})
    return shots, pcm, t + pace["end"]


def write_mix(path, shots, pcm, duration):
    """Lines and effects are added together, so an effect can play under a voice."""
    mix = array("i", bytes(int(duration * RATE) * 4))
    for shot in shots:
        for item, gain in [(l, 1.0) for l in shot["lines"]] + [(f, f["gain"]) for f in shot.get("sfx", [])]:
            at = int(item["start"] * RATE)
            samples = array("h", pcm[item["id"]])
            for n, value in enumerate(samples[:max(0, len(mix) - at)]):
                mix[at + n] += int(value * gain)
    out = array("h", (max(-32768, min(32767, v)) for v in mix))
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(out.tobytes())


def write_page(path, wav, cfg, shots, duration):
    with tempfile.TemporaryDirectory() as tmp:
        m4a = Path(tmp) / "audio.m4a"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(wav), "-c:a", "aac", "-b:a", "96k",
                        "-movflags", "+faststart", str(m4a)], check=True)
        audio = base64.b64encode(m4a.read_bytes()).decode()
    data = {"id": cfg["id"], "title": cfg["title"], "duration": round(duration, 3),
            "scenes": [{"title": s["title"], "setting": s.get("setting", "")} for s in cfg["scenes"]],
            "speakers": {k: v.get("name", k) for k, v in cfg["voices"].items()}, "shots": shots}
    page = (TOOL / "player.html").read_text(encoding="utf-8")
    page = page.replace("__EPISODE_DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    path.write_text(page.replace("__AUDIO_BASE64__", audio), encoding="utf-8")


def write_timeline(ep, cfg, shots, duration):
    """<episode>/timeline.json: the same timing in frames, the contract for the Blender build."""
    fps = cfg.get("fps", 24)
    frame = lambda t: round(t * fps) + 1
    total = round(duration * fps)
    out = []
    for i, s in enumerate(shots):
        lines = [{"id": l["id"], "who": l["who"], "text": l["text"], "how": l["how"],
                  "file": l["file"], "first_frame": frame(l["start"]),
                  "last_frame": max(frame(l["start"]), frame(l["end"]) - 1)} for l in s["lines"]]
        out.append({"id": s["id"], "scene": s["scene"] + 1, "setting": cfg["scenes"][s["scene"]].get("setting", ""),
                    "framing": s["framing"], "camera": s["camera"], "action": s["action"], "why": s["why"],
                    "sound": s["sound"], "caption": s["caption"],
                    "transition": s.get("transition"),
                    "sfx": [{"id": f["id"], "file": f["file"], "gain": f["gain"], "first_frame": frame(f["start"])} for f in s.get("sfx", [])],
                    "first_frame": 1 if i == 0 else frame(s["start"]),
                    "last_frame": total if i == len(shots) - 1 else frame(shots[i + 1]["start"]) - 1, "lines": lines})
    data = {"id": cfg["id"], "title": cfg["title"], "fps": fps, "frame_start": 1, "frame_end": total, "shots": out}
    (ep / "timeline.json").write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Build the audio version of an episode")
    ap.add_argument("episode", type=Path)
    ap.add_argument("--force", nargs="*", default=[], help="line ids to voice again")
    ap.add_argument("--no-voices", action="store_true", help="do not call the TTS")
    args = ap.parse_args()
    ep = args.episode.resolve()
    require_approved_script(ep)
    cfg = load_config(ep)
    if not args.no_voices:
        make_voices(ep, cfg, args.force)
    shots, pcm, duration = build_timeline(ep, cfg)
    wav = ep / "renders" / f"{cfg['id']}-audio.wav"
    page = ep / "renders" / f"{cfg['id']}-preview.html"
    write_mix(wav, shots, pcm, duration)
    write_page(page, wav, cfg, shots, duration)
    write_timeline(ep, cfg, shots, duration)
    print(f"{len(shots)} shots, {len(pcm)} lines, {duration:.1f} s")
    print(page)


if __name__ == "__main__":
    main()
