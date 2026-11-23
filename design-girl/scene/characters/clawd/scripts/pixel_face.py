"""Clawd's block face: eyes and mouth made of square pixels on the 0.05 grid of his body.

Built in the episode file at build time; clawd.blend is never edited. One object per shape, parented to the body bone
like the model's own eyes, in the model's eye material. A shape is shown by constant keys on its visibility.

    face = pixel_face.build(rig, old_eye_objects, collection, "EP3_Clawd_")
    mouth = {frame: "flat", ...}
    pixel_face.lip_sync(mouth, line_first_frame, pixel_face.read_envelope(wav, n_frames, fps))
    face.key(eye_track, mouth)

Eye art is drawn for the eye on the viewer's left, with the nose side on the right; the other eye is its mirror.
"""
import wave

import bpy
import numpy as np

PIXEL = 0.05
FACE_Y = -0.2             # front of the body, in the eye meshes' local space
DEPTH = 0.007             # how far a pixel stands out of the face, as on the model's eyes
EYE_X = 0.25
EYE_TOP = 0.50
MOUTH_TOP = 0.25

EYES = {
    "neutral":   ("....", ".##.", ".##.", ".##."),
    "blink":     ("...", "...", "###", "..."),
    "wide":      ("###", "###", "###", "###"),
    "attentive": ("...", "##.", "###", "###"),     # lid slopes down to the nose
    "narrowed":  ("...", "###", "###", "..."),
    "concerned": ("...", ".##", "###", "###"),     # lid slopes up to the nose
    "happy":     ("...", ".#.", "#.#", "..."),
    "soft":      ("....", ".##.", "#..#", "...."),
}

# A short, restrained mouth: always the same width, it only opens downward by a block or two. No smiles: warmth is in the eyes.
MOUTHS = {
    "flat":   ("...", "###", "...", "..."),
    "slight": ("...", "###", "###", "..."),
    "open":   ("...", "###", "###", "###"),
}
LIP_LEVELS = (0.18, 0.65)  # envelope: below the first the mouth rests, above the second it is fully open


def fcurves_of(idb):
    ad = idb.animation_data
    if not ad or not ad.action:
        return
    for layer in ad.action.layers:
        for strip in layer.strips:
            bag = strip.channelbag(ad.action_slot)
            if bag:
                yield from bag.fcurves


# ---------------------------------------------------------------- voice
def read_mono(path):
    with wave.open(str(path)) as w:
        rate, channels, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
        x = np.frombuffer(w.readframes(w.getnframes()), {2: "<i2", 4: "<i4"}[width]).astype(np.float32)
    if channels > 1:
        x = x.reshape(-1, channels).mean(1)
    return rate, x


def voice_phrases(path, fps, min_frames=10, silence=0.02, voiced=0.1):
    """Spoken phrases of a wav as (first, last) frame offsets, split at real silences.

    A piece of voice shorter than min_frames is the far side of a consonant's closure, so it joins its neighbour.
    """
    rate, x = read_mono(path)
    hop = rate / fps / 2
    peak = np.percentile(np.abs(x), 99) or 1.0
    level = [float(np.sqrt(np.mean(x[int(i * hop):int((i + 1) * hop)] ** 2))) / peak for i in range(int(len(x) / hop))]
    runs, start = [], None
    for i, v in enumerate(level + [0.0]):
        if v >= silence and start is None:
            start = i
        elif v < silence and start is not None:
            if max(level[start:i]) >= voiced:
                runs.append([start, i - 1])
            start = None
    phrases = []
    for run in runs:
        if phrases and (run[1] - run[0] < 2 * min_frames or phrases[-1][1] - phrases[-1][0] < 2 * min_frames):
            phrases[-1][1] = run[1]
        else:
            phrases.append(run)
    return [(a // 2, b // 2) for a, b in phrases]


def read_envelope(path, frames, fps):
    """Per-frame loudness of a wav, 0..1, with a quick attack and a soft release."""
    rate, x = read_mono(path)
    hop = rate / fps
    rms = np.array([np.sqrt(np.mean(x[int(i * hop):int((i + 1) * hop)] ** 2))
                    if int(i * hop) < len(x) - 1 else 0.0 for i in range(frames)])
    peak = np.percentile(rms, 95) or 1.0
    target = np.clip((rms / peak - 0.12) / 0.88, 0.0, 1.0)
    out, v = [], 0.0
    for t in target:
        v += (t - v) * (0.7 if t > v else 0.3)
        out.append(float(v))
    return out


def lip_sync(mouth, first, envelope, step=2):
    """Overlays speech on a {frame: resting shape} track, changing shape on twos so it reads and does not flicker."""
    for i in range(0, len(envelope), step):
        level = max(envelope[i:i + step])
        for f in range(first + i, first + min(i + step, len(envelope))):
            if level >= LIP_LEVELS[0]:
                mouth[f] = "slight" if level < LIP_LEVELS[1] else "open"


# ---------------------------------------------------------------- geometry
def rectangles(art):
    """Filled pixels of the art as (col0, col1, row0, row1) boxes, merging runs so faces stay clean."""
    open_boxes, boxes = {}, []
    for r, line in enumerate(art):
        runs, c = [], 0
        while c < len(line):
            if line[c] == "#":
                start = c
                while c < len(line) and line[c] == "#":
                    c += 1
                runs.append((start, c))
            else:
                c += 1
        current = {}
        for run in runs:
            current[run] = open_boxes.pop(run, r)
        boxes += [(a, b, top, r) for (a, b), top in open_boxes.items()]
        open_boxes = current
    boxes += [(a, b, top, len(art)) for (a, b), top in open_boxes.items()]
    return boxes


def add_box(verts, faces, x0, x1, z0, z1):
    y0, y1 = FACE_Y - DEPTH, FACE_Y
    n = len(verts)
    verts += [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
              (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    faces += [tuple(n + i for i in q) for q in
              ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7))]


def art_center(art):
    cols = [c for line in art for c, ch in enumerate(line) if ch == "#"]
    return (min(cols) + max(cols) + 1) / 2


def add_art(verts, faces, art, center_x, top, mirror=False):
    mid = art_center(art)
    for a, b, r0, r1 in rectangles(art):
        x0, x1 = (a - mid) * PIXEL, (b - mid) * PIXEL
        if mirror:
            x0, x1 = -x1, -x0
        add_box(verts, faces, center_x + x0, center_x + x1, top - r1 * PIXEL, top - r0 * PIXEL)


def eye_geometry(art):
    verts, faces = [], []
    add_art(verts, faces, art, -EYE_X, EYE_TOP)
    add_art(verts, faces, art, EYE_X, EYE_TOP, mirror=True)
    return verts, faces


def mouth_geometry(art):
    verts, faces = [], []
    add_art(verts, faces, art, 0.0, MOUTH_TOP)
    return verts, faces


# ---------------------------------------------------------------- the face
class PixelFace:
    def __init__(self, eyes, mouths):
        self.eyes = eyes
        self.mouths = mouths

    def key(self, eye_track, mouth_track):
        _key_track(self.eyes, eye_track)
        _key_track(self.mouths, mouth_track)


def _key_visible(ob, frame, visible):
    ob.hide_render = ob.hide_viewport = not visible
    ob.keyframe_insert("hide_render", frame=frame)
    ob.keyframe_insert("hide_viewport", frame=frame)


def _key_track(objects, track):
    previous = None
    for f in sorted(track):
        shape = track[f]
        if shape == previous:
            continue
        for name in (objects if previous is None else (previous, shape)):
            _key_visible(objects[name], f, name == shape)
        previous = shape
    for ob in objects.values():
        for fc in fcurves_of(ob):
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT"
        ob.animation_data.action.name = ob.name


def _shape_object(name, geometry, material, template, rig, collection):
    verts, faces = geometry
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.materials.append(material)
    mesh.update()
    ob = bpy.data.objects.new(name, mesh)
    collection.objects.link(ob)
    ob.parent = rig
    ob.parent_type = "BONE"
    ob.parent_bone = template.parent_bone
    ob.matrix_parent_inverse = template.matrix_parent_inverse.copy()
    ob.matrix_basis = template.matrix_basis.copy()
    return ob


def build(rig, old_eyes, collection, prefix):
    """Replaces the model's eye objects with the full set of pixel eyes and mouths."""
    template = old_eyes[0]
    material = template.data.materials[0]
    eyes = {n: _shape_object(f"{prefix}Eyes_{n}", eye_geometry(a), material, template, rig, collection)
            for n, a in EYES.items()}
    mouths = {n: _shape_object(f"{prefix}Mouth_{n}", mouth_geometry(a), material, template, rig, collection)
              for n, a in MOUTHS.items()}
    for ob in old_eyes:
        mesh = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    return PixelFace(eyes, mouths)
