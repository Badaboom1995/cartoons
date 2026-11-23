"""Episode 1 "Сделай красиво": the timeline, in frames (24 fps, 25 s, 9:16). Pure Python.

Single source of truth for both scripts/make_episode1.py (screen images, overlays, sounds)
and scripts/episode1.py (cameras, cuts, animation). Frame 1 = 0.00 s; t seconds = frame 1 + 24 t.
"""
FPS = 24
FRAME_END = 600            # 25 s


def fr(t):
    """First frame at time t (seconds)."""
    return int(round(t * FPS)) + 1


PROMPT_1 = "сделай красиво"
PROMPT_2 = "Минимализм, белый фон, персиковые акценты, как на референсе"
CLAUDE_1 = "Сейчас сделаю!"
CAPTION_1 = "Мой первый сайт"
CARD_LABEL = "Совет:"
CARD_TEXT = "описывай стиль словами и прикладывай референс. „Красиво“ все понимают по-разному"

# shots: (scenario scene, camera key, first frame, last frame). Scene 7 is split: the screen only
# faces her, so the site turning clean is a screen close-up, then the front two-shot for her smile.
SHOTS = [
    (1, "S1_Medium", fr(0), fr(4) - 1),
    (2, "S2_Keys", fr(4), fr(7) - 1),
    (3, "S3_Claude", fr(7), fr(10) - 1),
    (4, "S4_Screen", fr(10), fr(13) - 1),
    (5, "S5_Face", fr(13), fr(15) - 1),
    (6, "S6_Shoulder", fr(15), fr(19) - 1),
    (7, "S4_Screen", fr(19), fr(20.25) - 1),
    (7, "S7_Front", fr(20.25), fr(22) - 1),
    (8, "Card", fr(22), FRAME_END),
]

# ---- key moments
KEYS_1 = [fr(4.3) + round(i * (fr(6.25) - fr(4.3)) / (len(PROMPT_1) - 1)) for i in range(len(PROMPT_1))]
ENTER_1 = fr(6.5)            # decisive Enter (the click sound sits here)
CLAUDE_GLOW = fr(7.1)        # Clawd lights up
CLAUDE_REPLY = fr(7.4)       # "Сейчас сделаю!" (bubble and chat)
RAINBOW = (fr(10), fr(13))   # rainbow site + disco, [start, end) - the music cuts at 13 s exactly
RAINBOW_STEP = 3             # frames per rainbow animation state
EDIT_START = fr(15)          # old prompt back in the input, to be erased
ERASE = [fr(15.15) + 3 * i for i in range(5)]              # 14 chars, 3 at a time
TYPE_2 = [fr(15.85) + round(i * 2.4) for i in range(20)]    # 59 chars, 3 at a time
DRAG = [fr(17.9) + 3 * i for i in range(6)]                 # reference image dragged to the chat
DROP = fr(18.65)             # dropped: attachment chip (pop sound)
ENTER_2 = fr(18.8)           # sends the new prompt
WIPE = [fr(19.25) + 4 * i for i in range(3)]               # site turns clean, top down
CLEAN = fr(19.75)            # clean site (chime)
SMILE = fr(20.25)            # front two-shot: smile; thumbs up a little later
THUMB = (fr(20.5), fr(21.7))


def screen_states():
    """[(first frame, state)] in time order; a state holds until the next one.
    state = dict(site, chat (tuple of messages), input, drag (0..1 or None), attach)."""
    out = []

    def put(f, **kw):
        prev = dict(out[-1][1]) if out else dict(site="grey", chat=(), input="", drag=None, attach=False)
        prev.update(kw)
        out.append((f, prev))

    put(1)
    for i, f in enumerate(KEYS_1):
        put(f, input=PROMPT_1[:i + 1])
    put(ENTER_1 + 1, input="", chat=(("user", PROMPT_1),))
    put(CLAUDE_REPLY, chat=(("user", PROMPT_1), ("claude", CLAUDE_1)))
    for k, f in enumerate(range(RAINBOW[0], RAINBOW[1], RAINBOW_STEP)):
        put(f, site="rainbow%d" % (k % 4))
    put(RAINBOW[1], site="rainbow0")                       # music stops: the page freezes
    put(EDIT_START, input=PROMPT_1)
    n = len(PROMPT_1)
    for i, f in enumerate(ERASE):
        put(f, input=PROMPT_1[:max(0, n - 3 * (i + 1))])
    for i, f in enumerate(TYPE_2):
        put(f, input=PROMPT_2[:min(len(PROMPT_2), 3 * (i + 1))])
    for i, f in enumerate(DRAG):
        put(f, drag=(i + 1) / len(DRAG))
    put(DROP, drag=None, attach=True)
    chat2 = (("user", PROMPT_1), ("claude", CLAUDE_1), ("user", PROMPT_2))
    put(ENTER_2 + 1, input="", attach=False, chat=chat2)
    for i, f in enumerate(WIPE):
        put(f, site="wipe%d" % (i + 1))
    put(CLEAN, site="clean")
    return out


def state_key(s):
    """Stable file stem for a state."""
    import hashlib
    raw = repr((s["site"], s["chat"], s["input"], s["drag"], s["attach"])).encode()
    return "screen_" + hashlib.sha1(raw).hexdigest()[:10]


def screen_timeline():
    """[(first, last, file name)] covering frames 1..FRAME_END, merged runs of the same image."""
    st = screen_states()
    runs = []
    for n, (f, s) in enumerate(st):
        last = (st[n + 1][0] - 1) if n + 1 < len(st) else FRAME_END
        name = state_key(s) + ".png"
        if runs and runs[-1][2] == name:
            runs[-1] = (runs[-1][0], last, name)
        else:
            runs.append((f, last, name))
    return runs


# sounds: (file, first frame)
def sound_cues():
    cues = [("tick.wav", f) for f in KEYS_1]
    cues += [("enter.wav", ENTER_1), ("chime.wav", CLAUDE_GLOW), ("disco.wav", RAINBOW[0])]
    cues += [("tick.wav", f) for f in ERASE + TYPE_2]
    cues += [("pop.wav", DROP), ("enter.wav", ENTER_2), ("chime.wav", CLEAN)]
    return cues


DISCO_FRAMES = RAINBOW[1] - RAINBOW[0]   # the disco loop is exactly this long, so it cuts at 13 s
