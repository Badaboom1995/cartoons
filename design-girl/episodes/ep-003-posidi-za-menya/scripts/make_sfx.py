#!/usr/bin/env python3
"""Small original sound effects of EP3: the call-join chime and a keyboard key click. Writes audio/sfx/*.wav."""
import math
import random
import struct
import wave
from pathlib import Path

RATE = 24000
OUT = Path(__file__).resolve().parents[1] / "audio" / "sfx"


def save(name, samples):
    OUT.mkdir(parents=True, exist_ok=True)
    with wave.open(str(OUT / name), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, s)) * 32767)) for s in samples))


def bell(t, freq):
    if t < 0:
        return 0.0
    attack = min(1.0, t / 0.008)
    return attack * math.exp(-t * 6.5) * (math.sin(2 * math.pi * freq * t) + 0.22 * math.sin(4 * math.pi * freq * t))


def join():
    """Two soft rising notes."""
    return [0.2 * (bell(n / RATE, 587.33) + bell(n / RATE - 0.16, 880.0)) for n in range(int(RATE * 0.85))]


def key():
    """A short plastic tick with a low thunk under it."""
    rng = random.Random(3)
    out, last = [], 0.0
    for n in range(int(RATE * 0.07)):
        t = n / RATE
        noise = rng.uniform(-1, 1)
        high, last = noise - last, noise
        out.append(0.34 * high * math.exp(-t * 260) + 0.3 * math.sin(2 * math.pi * 170 * t) * math.exp(-t * 90))
    return out


if __name__ == "__main__":
    save("join.wav", join())
    save("key.wav", key())
