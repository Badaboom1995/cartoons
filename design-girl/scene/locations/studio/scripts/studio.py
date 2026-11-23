"""Builds "The Designer's studio" voxel room in Blender (static set: geometry, materials, lights, cameras).

Run inside Blender:
    exec(compile(open(".../scene/locations/studio/scripts/studio.py").read(), "studio.py", "exec"), {"__name__": "studio"})
Everything is rebuilt from scratch in a scene called "Studio". Only the "Studio" scene and datablocks
prefixed "STU_" are touched; other scenes (Port, Designer, Mascot) are left alone.
Exec with any other __name__ to only define the helpers (set_desk, set_lighting, set_lamp, render_cam, ...).

Conventions match designer.py: 1 voxel = 0.04 m, Z up, metres in code. The character sits/stands at
STU_Character_Anchor facing -Y (towards the cameras); her LEFT is +X. The desk is between her and the
cameras, the poster wall is behind her (+Y), the window is in the left wall (-X, her right), the shelf
is on the back wall to the camera's left, the floor lamp in the back-right corner.

Room interior: x -1.6..1.6, y -3.0..1.6 (back wall), z 0..2.8.

Animatable controls (also stored as custom properties, exported as glTF extras):
  desk height  STU_Desk_Lift.location.z     (sitting_z 0.72, standing_z 0.92)
  lamp colour  STU_Lamp_Light_A.data.color  + material STU_lamp_glow   (gradient start, default #F5B38A)
               STU_Lamp_Light_B.data.color  + material STU_lamp_glow_B (gradient end, default #C9A7F0)
               (set_lamp(a, b) sets all four; presets in STU_Floor_Lamp["moods"])
  day/evening  set_lighting("day"|"evening"): day = STU_Lights_Day on, STU_Lights_Evening and
               STU_Lights_Lamp hidden, lamp glow materials Emission Strength 0; evening = the reverse.
               It also recolours the self-lit city in STU_Exterior (materials with "exterior" = True swap
               Emission Color between their "day_color" and "evening_color" extras: sky, buildings, windows)
  chair        STU_Chair (root, in STU_Desk; hide for standing) > STU_Chair_Seat (swivel: rotation_euler.z)
  dock glow    material STU_dock_glow  Emission Strength (glTF emissive_strength)
  screens      materials STU_screen_laptop / STU_screen_tablet / STU_screen_phone: black base colour,
               image in Emission Color (glTF emissiveTexture), Emission Strength = brightness
"""
import math
import os
import random

import bpy
from mathutils import Matrix, Vector

REPO = "/Users/alexey/.paradev/projects/cartoons"
STUDIO_DIR = os.path.join(REPO, "design-girl", "scene", "locations", "studio")
TEX_DIR = os.path.join(STUDIO_DIR, "textures")
BLEND_PATH = os.path.join(STUDIO_DIR, "studio.blend")

S = 0.04            # metres per voxel
H = S / 2           # half voxel, for small desk/shelf objects
PREFIX = "STU_"
SCENE = "Studio"

# room interior (metres)
RX0, RX1 = -1.6, 1.6
RY0, RY1 = -3.0, 1.6
RZ = 2.8
WT = 0.08           # wall thickness
WIN_Y = (-1.4, 0.2)
WIN_Z = (0.80, 2.40)

DESK_SIT, DESK_STAND = 0.72, 0.92   # standing fitted to her elbows (shoulders at 1.0 m), see report
LAMP_XY = (1.42, 1.42)
LAMP_HEAD_Z = 1.78
DESK_W, DESK_D = 1.52, 0.72
LAPTOP_SCALE = 1.3   # laptop (and its screen) scaled up so it reads next to her chunky voxel body
LEG_X = 0.62

PALETTE = {
    "wall": "#DEDCDA",   # was #F7F5F2; 10% darker so the Designer reads against it
    "floor": "#E3D5C3", "floor2": "#DDCDB8",
    "desk": "#BE8A5F", "desk2": "#B6825A", "desk_grain": "#9F6D47",     # warm oak tabletop
    "leg": "#1E1E1E", "wood": "#D9B48F",
    # accents (all from the series): sage (succulents), terracotta/coral (Claude orange, headphones),
    # peach (lamp), plus a little cobalt (ribbon) as the pop
    "sage": "#72977C",   # was #7FA88A; 10% darker, same reason
    "sage_dark": "#5B8468", "terra": "#D97757", "coral": "#EE9E78",
    "peach": "#F5B38A", "cobalt": "#1769FF", "paper": "#F4EEE6",
    "tech": "#C9CCD1", "tech_light": "#DCDFE3", "screen": "#FFFFFF", "frame": "#1E1E1E",
    "frame_pink": "#EA4C89",          # the one coloured poster frame (Chtoby, echoes its pink "?")
    "succ": "#7FA88A", "succ_dark": "#5B8468", "tea": "#B9C98A",
    "ball": "#EA4C89", "ball_seam": "#B8326A", "ribbon": "#1769FF",
    "white": "#FFFFFF", "ceramic": "#ECE7E0", "graphite": "#3A3C40", "keys_dark": "#2B2D31",
    "bezel": "#151515", "soil": "#6E5B4B", "palo": "#CFA978", "palo_burnt": "#3B302A",
    "steam": "#FFFFFF", "smoke": "#E4E1DE", "glass": "#E9F1F5",
    "dock_glow": "#E8875F", "lamp_glow": "#F5B38A", "lamp_glow_B": "#C9A7F0",
}
ALPHA = {"steam": 0.55, "smoke": 0.5, "glass": 0.28}
EMISSION = {"dock_glow": 1.0, "lamp_glow": 6.0, "lamp_glow_B": 6.0}
LAMP_A, LAMP_B = "#F5B38A", "#C9A7F0"
DAY = {  # day setup: warm, soft window key + minimal shadowless fill (W for the area light, W/m2 for suns)
    "window_area": 24.0, "window_sun": 0.12, "fill": 2.3, "sky": 0.8, "bounce": 0.35, "wall_bounce": 1.1,
    "wall_spill": 0.9,
    "window_color": "#FFEAD3", "sun_color": "#FFDDB6",
}

# ---- city outside the window (STU_Exterior). Everything there is self-lit (black base, emission = colour),
# casts no shadows, and switches day/evening through set_lighting (colours stored on each material as
# "day_color" / "evening_color" extras so three.js can do the same).
GROUND_Z = -9.0          # the studio is a few floors up
SKY_X = -45.0
SKY_BANDS = [  # (z0, z1, day, evening): stepped voxel gradient, horizon first
    (-40, 0, "#F3E7DB", "#F2A57E"), (0, 3, "#EAE8E3", "#E6907F"), (3, 6, "#DDE6EE", "#CC8090"),
    (6, 9, "#CFE0EF", "#A3719A"), (9, 12, "#C0D7EE", "#755F98"), (12, 16, "#B0CEEB", "#4A4C84"),
    (16, 90, "#A1C5E8", "#2D3566"),
]
CITY_ROWS = [  # (name, front x, y range, width range, depth range, top z range, window pitch (x, z), colours)
    ("Near", -7.0, (-18, 18), (2.4, 4.0), (3, 5), (-3.5, 1.5), (0.9, 1.1),
     [("#D7A58E", "#3C3A56"), ("#C9C1B6", "#44425F"), ("#A9BCAB", "#38445A")]),
    ("Mid", -14.0, (-26, 26), (3.0, 5.5), (4, 7), (-1.0, 7.0), (1.0, 1.2),
     [("#D9CDBE", "#4B4A6B"), ("#B7C3D0", "#47506F"), ("#CDB8A6", "#554D6D")]),
    ("Far", -25.0, (-36, 36), (4.0, 7.5), (5, 9), (3.0, 13.0), (1.2, 1.4),
     [("#CED7E1", "#5E5A80"), ("#D8DCE2", "#655D82"), ("#C4CEDA", "#585E84")]),
]
CITY_WIN = {  # per row: (day glass, evening lit, evening dark)
    "Near": ("#9DB2C7", "#FFD38A", "#2A2B45"), "Mid": ("#AFC0D2", "#FFD38A", "#33344F"),
    "Far": ("#C3CFDC", "#F9CC88", "#44425F"),
}
CITY_LIT = 0.35          # share of windows that light up in the evening
CITY_GROUND = ("#B9B1A7", "#24263A")
LAMP_MOODS = {  # suggested gradient presets (start, end); stored on the lamp as extras
    "calm": ("#F5B38A", "#C9A7F0"), "focus": ("#8F7CF0", "#5FA8F0"),
    "panic": ("#F0503C", "#C0306A"), "acid": ("#3CF0A0", "#F03CC8"),
}

TEXTURES = {  # key: (file, fallback colour, width px, height px)
    "poster_eyechart": ("poster_eyechart.png", "#FDFCFA", 1200, 1800),
    "poster_lorem": ("poster_lorem.png", "#FDFCFA", 1200, 1800),
    "poster_chtoby": ("poster_chtoby.png", "#FDFCFA", 1200, 1800),
    "poster_kerning": ("poster_kerning.png", "#FDFCFA", 1200, 1800),
    "poster_rams": ("poster_rams.png", "#FDFCFA", 1200, 1800),
    "screen_laptop": ("screen_laptop.png", "#FFFFFF", 1600, 1000),
    "screen_tablet": ("screen_focus_tablet.png", "#000000", 1200, 1600),
    "screen_phone": ("screen_focus_phone.png", "#000000", 900, 1950),
    "plaque": ("plaque_awwwards.png", "#E9E4DA", 1200, 300),
    "ribbon_img": ("ribbon_featured.png", "#1769FF", 800, 1000),
}
SCREEN_EMISSION = 1.0


# ---------------------------------------------------------------- colour / materials
def _lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_rgba(h, a=1.0):
    h = h.lstrip("#")
    return tuple(_lin(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4)) + (a,)


def _bsdf(m):
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None) or nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(bsdf.outputs[0], out.inputs[0])
    bsdf.inputs["Roughness"].default_value = 1.0
    for name in ("Specular IOR Level", "Specular"):
        if name in bsdf.inputs:
            bsdf.inputs[name].default_value = 0.0
    return bsdf


def _blend(m):
    for attr, val in (("surface_render_method", "BLENDED"), ("blend_method", "BLEND"),
                      ("use_backface_culling", False)):
        try:
            setattr(m, attr, val)
        except Exception:
            pass


def make_material(key):
    m = bpy.data.materials.new(PREFIX + key)
    bsdf = _bsdf(m)
    col = hex_rgba(PALETTE[key])
    bsdf.inputs["Base Color"].default_value = col
    a = ALPHA.get(key, 1.0)
    if a < 1.0:
        bsdf.inputs["Alpha"].default_value = a
        _blend(m)
    if key in EMISSION:
        bsdf.inputs["Emission Color"].default_value = col
        bsdf.inputs["Emission Strength"].default_value = EMISSION[key]
    m.diffuse_color = col[:3] + (a,)
    return m


def shade_hex(h, f):
    """sRGB hex scaled by f (darker < 1 < lighter), clamped."""
    h = h.lstrip("#")
    return "#" + "".join("%02X" % max(0, min(255, round(int(h[i:i + 2], 16) * f))) for i in (0, 2, 4))


def ext_material(key, day, evening):
    """Self-lit exterior material: black base, emission = colour (strength 1), day/evening colours as extras."""
    m = bpy.data.materials.new(PREFIX + key)
    bsdf = _bsdf(m)
    bsdf.inputs["Base Color"].default_value = (0, 0, 0, 1)
    bsdf.inputs["Emission Color"].default_value = hex_rgba(day)
    bsdf.inputs["Emission Strength"].default_value = 1.0
    m["day_color"], m["evening_color"], m["exterior"] = day, evening, True
    m.diffuse_color = hex_rgba(day)
    return m


def load_image(key):
    """Returns the STU_ image for a texture key, or None if the file is not there (yet)."""
    fname = TEXTURES[key][0]
    path = os.path.join(TEX_DIR, fname)
    if not os.path.isfile(path):
        return None
    try:
        img = bpy.data.images.load(path, check_existing=False)
    except Exception:
        return None
    img.name = PREFIX + os.path.splitext(fname)[0]
    return img


def image_material(key, emission=0.0):
    """Flat material with an image texture (Base Color, and Emission for screens). Falls back to a flat colour."""
    m = bpy.data.materials.new(PREFIX + key)
    bsdf = _bsdf(m)
    fallback = hex_rgba(TEXTURES[key][1])
    bsdf.inputs["Base Color"].default_value = fallback
    img = load_image(key)
    m["texture_file"] = TEXTURES[key][0]
    m["placeholder"] = img is None
    if img is not None:
        nt = m.node_tree
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = img
        tex.interpolation = "Linear"
        tex.location = (-400, 200)
        if emission > 0:   # screens are self-lit: black base, the image drives the emission only
            bsdf.inputs["Base Color"].default_value = (0, 0, 0, 1)
            nt.links.new(tex.outputs["Color"], bsdf.inputs["Emission Color"])
        else:
            nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    elif emission > 0:
        bsdf.inputs["Emission Color"].default_value = fallback
    if emission > 0:
        bsdf.inputs["Emission Strength"].default_value = emission
    m.diffuse_color = fallback
    return m


# ---------------------------------------------------------------- geometry helpers (metres)
FACES = [
    ((1, 0, 0), [(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)]),
    ((-1, 0, 0), [(0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0)]),
    ((0, 1, 0), [(0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0)]),
    ((0, -1, 0), [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)]),
    ((0, 0, 1), [(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]),
    ((0, 0, -1), [(0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)]),
]


class Geo:
    """Collects quads (4 points in world metres + material key)."""

    def __init__(self):
        self.quads = []

    def box(self, x0, y0, z0, x1, y1, z1, m):
        lo, sz = (x0, y0, z0), (x1 - x0, y1 - y0, z1 - z0)
        for _, corners in FACES:
            self.quads.append(([tuple(lo[a] + c[a] * sz[a] for a in range(3)) for c in corners], m))
        return self

    def box6(self, x0, y0, z0, x1, y1, z1, m, front=None, side=None, top=None):
        """Box with its own material for the +X face (front), the +-Y faces (side) and +Z (top)."""
        lo, sz = (x0, y0, z0), (x1 - x0, y1 - y0, z1 - z0)
        for nrm, corners in FACES:
            k = {(1, 0, 0): front, (0, 1, 0): side, (0, -1, 0): side, (0, 0, 1): top}.get(nrm) or m
            self.quads.append(([tuple(lo[a] + c[a] * sz[a] for a in range(3)) for c in corners], k))
        return self

    def obox(self, M, x0, y0, z0, x1, y1, z1, m):
        """Box given in the local frame M (Matrix, metres)."""
        lo, sz = (x0, y0, z0), (x1 - x0, y1 - y0, z1 - z0)
        for _, corners in FACES:
            self.quads.append(([tuple(M @ Vector([lo[a] + c[a] * sz[a] for a in range(3)])) for c in corners], m))
        return self

    def vox(self, cells, cell, origin, M=None):
        """cells {(i,j,k): mat}; cell = size or (sx,sy,sz); cell (i,j,k) min corner = origin + idx*cell.
        Only faces not hidden by a neighbour are kept (transparent cells never hide opaque ones)."""
        cs = cell if isinstance(cell, (tuple, list)) else (cell, cell, cell)
        ox, oy, oz = origin
        for (i, j, k), m in cells.items():
            for (dx, dy, dz), corners in FACES:
                n = cells.get((i + dx, j + dy, k + dz))
                if n is not None and (n not in ALPHA or n == m):
                    continue
                pts = [(ox + (i + a) * cs[0], oy + (j + b) * cs[1], oz + (k + c) * cs[2]) for a, b, c in corners]
                if M is not None:
                    pts = [tuple(M @ Vector(p)) for p in pts]
                self.quads.append((pts, m))
        return self


def circle(n, i0=None):
    """(i, j) cells of a voxel disc n cells across, centred on (0, 0) (cells -n/2 .. n/2-1 for even n)."""
    r = n / 2.0
    out = []
    lo = -(n // 2)
    for i in range(lo, lo + n):
        for j in range(lo, lo + n):
            ci = i + 0.5 - (0 if n % 2 == 0 else 0.5)
            cj = j + 0.5 - (0 if n % 2 == 0 else 0.5)
            if ci * ci + cj * cj <= r * r - 0.05:
                out.append((i, j))
    return out


def ring(n, inner):
    ins = set(circle(inner))
    return [c for c in circle(n) if c not in ins]


def Rx(deg):
    return Matrix.Rotation(math.radians(deg), 4, "X")


def Rz(deg):
    return Matrix.Rotation(math.radians(deg), 4, "Z")


def T(x, y, z):
    return Matrix.Translation((x, y, z))


# ---------------------------------------------------------------- builder
def cleanup():
    """Remove only the Studio scene and STU_ datablocks."""
    sc = bpy.data.scenes.get(SCENE)
    if sc:
        win = bpy.context.window
        if win and win.scene == sc:
            other = next((s for s in bpy.data.scenes if s != sc), None)
            if other:
                win.scene = other
        for o in list(sc.collection.all_objects):
            if o.name.startswith(PREFIX):
                bpy.data.objects.remove(o, do_unlink=True)
        for c in list(sc.collection.children_recursive):
            if c.name.startswith(PREFIX):
                bpy.data.collections.remove(c)
        bpy.data.scenes.remove(sc)
    for o in list(bpy.data.objects):
        if o.name.startswith(PREFIX):
            bpy.data.objects.remove(o, do_unlink=True)
    for coll in (bpy.data.collections, bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras,
                 bpy.data.worlds, bpy.data.images):
        for d in list(coll):
            if d.name.startswith(PREFIX):
                coll.remove(d)


class Builder:
    def __init__(self):
        cleanup()
        self.mats = {}
        self.colls = {}
        self.world = {}       # object name -> world Matrix (as placed)
        self.scene = bpy.data.scenes.new(SCENE)

    def coll(self, name, parent=None):
        if name not in self.colls:
            c = bpy.data.collections.new(PREFIX + name)
            (self.colls[parent] if parent else self.scene.collection).children.link(c)
            self.colls[name] = c
        return self.colls[name]

    def mat(self, key):
        if key not in self.mats:
            self.mats[key] = make_material(key)
        return self.mats[key]

    def _link(self, ob, coll, M, parent):
        self.colls[coll].objects.link(ob)
        if parent is not None:
            ob.parent = parent
            ob.matrix_parent_inverse = Matrix.Identity(4)
            ob.matrix_basis = self.world[parent.name].inverted() @ M
        else:
            ob.matrix_basis = M
        self.world[ob.name] = M
        return ob

    def part(self, name, coll, geo, pivot=(0, 0, 0), parent=None, tags=None, M=None):
        """Mesh object from world-space quads with its origin at `pivot`; or, if M is given,
        from quads in local space placed with world matrix M."""
        verts, vindex, faces, fmats, slots = [], {}, [], [], []
        px, py, pz = pivot if M is None else (0, 0, 0)
        for pts, m in geo.quads:
            if m not in slots:
                slots.append(m)
            f = []
            for p in pts:
                key = (round(p[0] - px, 5), round(p[1] - py, 5), round(p[2] - pz, 5))
                if key not in vindex:
                    vindex[key] = len(verts)
                    verts.append(key)
                f.append(vindex[key])
            faces.append(f)
            fmats.append(slots.index(m))
        me = bpy.data.meshes.new(PREFIX + name)
        me.from_pydata(verts, [], faces)
        for m in slots:
            me.materials.append(self.mat(m) if isinstance(m, str) else m)
        me.polygons.foreach_set("material_index", fmats)
        me.update()
        ob = bpy.data.objects.new(PREFIX + name, me)
        for k, v in (tags or {}).items():
            ob[k] = v
        return self._link(ob, coll, T(*pivot) if M is None else M, parent)

    def plane(self, name, coll, w, h, material, M, parent=None, tags=None):
        """Flat w x h quad with UVs, in its local XZ plane, facing local -Y; world matrix M."""
        me = bpy.data.meshes.new(PREFIX + name)
        me.from_pydata([(-w / 2, 0, -h / 2), (w / 2, 0, -h / 2), (w / 2, 0, h / 2), (-w / 2, 0, h / 2)], [], [(0, 1, 2, 3)])
        uv = me.uv_layers.new(name="UVMap")
        for li, c in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]):
            uv.data[li].uv = c
        me.materials.append(material)
        me.update()
        ob = bpy.data.objects.new(PREFIX + name, me)
        for k, v in (tags or {}).items():
            ob[k] = v
        return self._link(ob, coll, M, parent)

    def empty(self, name, coll, M, parent=None, size=0.1, kind="PLAIN_AXES"):
        ob = bpy.data.objects.new(PREFIX + name, None)
        ob.empty_display_size = size
        ob.empty_display_type = kind
        return self._link(ob, coll, M, parent)

    def light(self, name, coll, kind, energy, color, M, **kw):
        ld = bpy.data.lights.new(PREFIX + name, kind)
        ld.energy = energy
        ld.color = hex_rgba(color)[:3]
        for k, v in kw.items():
            try:
                setattr(ld, k, v)
            except Exception:
                pass
        ob = bpy.data.objects.new(PREFIX + name, ld)
        return self._link(ob, coll, M, None)


def look_at(loc, target, roll_up=(0, 0, 1)):
    d = Vector(target) - Vector(loc)
    q = d.to_track_quat("-Z", "Y")
    return T(*loc) @ q.to_matrix().to_4x4()


def aim(loc, direction):
    q = Vector(direction).to_track_quat("-Z", "Y")
    return T(*loc) @ q.to_matrix().to_4x4()


# ================================================================ room
def build_room(B):
    c = "Room"
    # floor: light wood planks running towards the camera
    g = Geo()
    n = int(round((RX1 - RX0) / 0.16))
    for i in range(n):
        x0 = RX0 + i * 0.16
        g.box(x0, RY0 - WT, -WT, x0 + 0.16, RY1 + WT, 0.0, "floor2" if i % 3 == 1 else "floor")
    B.part("Floor", c, g, (0, 0, 0))
    B.part("Ceiling", c, Geo().box(RX0 - WT, RY0 - WT, RZ, RX1 + WT, RY1 + WT, RZ + WT, "wall"), (0, 0, RZ))
    B.part("Wall_Back", c, Geo().box(RX0 - WT, RY1, 0, RX1 + WT, RY1 + WT, RZ, "wall"), (0, RY1, 0))
    B.part("Wall_Front", c, Geo().box(RX0 - WT, RY0 - WT, 0, RX1 + WT, RY0, RZ, "wall"), (0, RY0, 0))
    B.part("Wall_Right", c, Geo().box(RX1, RY0, 0, RX1 + WT, RY1, RZ, "wall"), (RX1, 0, 0))
    g = Geo()                                                  # left wall with the window opening
    x0, x1 = RX0 - WT, RX0
    (wy0, wy1), (wz0, wz1) = WIN_Y, WIN_Z
    g.box(x0, RY0, 0, x1, wy0, RZ, "wall").box(x0, wy1, 0, x1, RY1, RZ, "wall")
    g.box(x0, wy0, 0, x1, wy1, wz0, "wall").box(x0, wy0, wz1, x1, wy1, RZ, "wall")
    B.part("Wall_Left", c, g, (RX0, 0, 0))

    # window: thin black frame, one mullion, one transom, white sill
    g = Geo()
    fx0, fx1, t = RX0 - 0.06, RX0 - 0.02, 0.03
    g.box(fx0, wy0, wz0, fx1, wy0 + t, wz1, "frame").box(fx0, wy1 - t, wz0, fx1, wy1, wz1, "frame")
    g.box(fx0, wy0, wz0, fx1, wy1, wz0 + t, "frame").box(fx0, wy0, wz1 - t, fx1, wy1, wz1, "frame")
    ym = (wy0 + wy1) / 2
    g.box(fx0, ym - t / 2, wz0, fx1, ym + t / 2, wz1, "frame")
    zt = wz0 + (wz1 - wz0) * 0.72
    g.box(fx0, wy0, zt - t / 2, fx1, wy1, zt + t / 2, "frame")
    g.box(RX0 - WT, wy0 - 0.04, wz0 - 0.02, RX0 + 0.06, wy1 + 0.04, wz0, "white")
    B.part("Window", c, g, (RX0, ym, wz0))

    # floor lamp in the back-right corner: black base, slim pole, upturned bowl with glowing inside
    lx, ly = LAMP_XY
    g = Geo()
    g.vox({(i, j, 0): "frame" for i, j in circle(6)}, (0.04, 0.04, 0.02), (lx, ly, 0))
    g.box(lx - 0.01, ly - 0.01, 0.02, lx + 0.01, ly + 0.01, 1.72, "frame")
    head = {(i, j, 0): "frame" for i, j in circle(4)}
    head.update({(i, j, 1): "frame" for i, j in ring(6, 4)})
    head.update({(i, j, 1): "lamp_glow" for i, j in ring(4, 2)})
    head.update({(i, j, 1): "lamp_glow_B" for i, j in circle(2)})
    g.vox(head, (0.04, 0.04, 0.03), (lx, ly, 1.72))
    lamp = B.part("Floor_Lamp", c, g, (lx, ly, 0),
                  tags={"lamp_color_a": LAMP_A, "lamp_color_b": LAMP_B,
                        "moods": str({k: list(v) for k, v in LAMP_MOODS.items()})})

    build_chair(B)
    return lamp


# ================================================================ work chair
CHAIR_XY = (0.0, 0.64)   # = STU_Character_Anchor
CHAIR_SEAT_Z = 0.44      # seat top (anchor "seat_z")
CHAIR_PIVOT_Z = 0.30     # swivel: STU_Chair_Seat rotates about its local Z here


def build_chair(B):
    """Ergonomic task chair: STU_Chair (root: five-star base, casters, gas shroud) and its child
    STU_Chair_Seat (chrome column, mechanism, seat, ribbed backrest, headrest, armrests) which swivels
    about Z. Terracotta shell, coral cushions, black frame. Hide STU_Chair for standing shots."""
    cx, cy = CHAIR_XY
    M0 = Matrix.Identity(4)                                  # geometry in the chair's local frame
    g = Geo()
    for k in range(5):                                       # five-star base, one leg towards the desk
        R = M0 @ Rz(-90 + k * 72)
        g.obox(R, 0.03, -0.022, 0.075, 0.29, 0.022, 0.105, "leg")
        g.obox(R, 0.26, -0.016, 0.06, 0.30, 0.016, 0.075, "leg")          # caster fork
        g.obox(R, 0.25, -0.014, 0.0, 0.31, 0.014, 0.06, "graphite")       # wheel
    g.vox({(i, j, 0): "leg" for i, j in circle(5)}, (0.02, 0.02, 0.06), (-0.01, -0.01, 0.06), M=M0)   # hub
    g.obox(M0, -0.028, -0.028, 0.12, 0.028, 0.028, CHAIR_PIVOT_Z, "leg")  # gas shroud
    chair = B.part("Chair", "Desk", g, M=T(cx, cy, 0),
                   tags={"note": "work chair; hide for standing shots. STU_Chair_Seat swivels (rotation Z)",
                         "seat_z": CHAIR_SEAT_Z})

    M1 = Matrix.Identity(4)                                  # seat assembly, local z 0 = swivel pivot
    sz0 = CHAIR_SEAT_Z - CHAIR_PIVOT_Z - 0.05                # seat shell bottom (local)
    g = Geo()
    g.obox(M1, -0.018, -0.018, 0.0, 0.018, 0.018, sz0 - 0.03, "tech")    # chrome gas column
    g.obox(M1, -0.11, -0.10, sz0 - 0.03, 0.11, 0.12, sz0, "leg")          # mechanism
    cells = {}
    for i in range(-6, 6):                                   # seat: 12 x 12 cells of 4 cm, rounded
        for j in range(-6, 6):
            ei, ej = abs(i + 0.5) > 5, abs(j + 0.5) > 5
            if not (ei and ej):
                cells[(i, j, 0)] = "terra"
            if abs(i + 0.5) < 5.5 - 0.5 and -6 <= j <= 4 and not (abs(i + 0.5) > 4 and (j == -6 or j == 4)):
                cells[(i, j, 1)] = "coral"
    g.vox(cells, (0.04, 0.04, 0.025), (0, 0.02, sz0), M=M1)
    # backrest: spine from the mechanism, then a reclined ribbed panel and a headrest
    g.obox(M1, -0.035, 0.10, sz0 - 0.03, 0.035, 0.30, sz0, "leg")
    g.obox(M1, -0.035, 0.27, sz0, 0.035, 0.31, sz0 + 0.20, "leg")
    Mb = M1 @ T(0, 0.30, sz0 + 0.14) @ Rx(-10)
    cells = {}
    for k in range(14):
        half = 6 if k < 5 else 5                              # wider lumbar, narrower upper back
        for i in range(-half, half):
            top_corner = k == 13 and abs(i + 0.5) > half - 1
            if not top_corner:
                cells[(i, 1, k)] = "terra"                    # shell (back)
            if abs(i + 0.5) < half - 1 and 0 < k < 13:
                cells[(i, 0, k)] = "terra" if k % 3 == 0 else "coral"   # ribbed cushion (front)
    g.vox(cells, (0.04, 0.03, 0.04), (0, -0.03, 0), M=Mb)
    g.obox(Mb, -0.02, 0.03, 0.50, 0.02, 0.055, 0.66, "leg")               # headrest stem
    cells = {}
    for i in range(-4, 4):
        for k in range(4):
            if not (abs(i + 0.5) > 3 and k in (0, 3)):
                cells[(i, 1, k)] = "terra"
                if abs(i + 0.5) < 3:
                    cells[(i, 0, k)] = "coral"
    g.vox(cells, (0.04, 0.03, 0.04), (0, -0.03, 0.62), M=Mb)
    for s in (-1, 1):                                         # T-armrests
        xa, xb = sorted((s * 0.10, s * 0.285))
        g.obox(M1, xa, -0.02, sz0 - 0.03, xb, 0.02, sz0 - 0.005, "leg")
        xa, xb = sorted((s * 0.255, s * 0.285))
        g.obox(M1, xa, -0.03, sz0 - 0.005, xb, 0.03, sz0 + 0.17, "leg")
        xa, xb = sorted((s * 0.235, s * 0.305))
        g.obox(M1, xa, -0.15, sz0 + 0.17, xb, 0.12, sz0 + 0.195, "graphite")
    B.part("Chair_Seat", "Desk", g, parent=chair, M=T(cx, cy, CHAIR_PIVOT_Z))
    return chair


# ================================================================ decor: accent wall, rug, floor plant
PANEL_X = 0.96           # half-width of the painted panel behind the poster grid
PANEL_TOP = 2.68


def build_decor(B):
    c = "Decor"
    # painted sage panel behind the posters, floor to near the ceiling, rounded (stepped) top corners
    g = Geo()
    yb, yf = RY1 - 0.004, RY1
    g.box(-PANEL_X, yb, 0.0, PANEL_X, yf, PANEL_TOP - 0.28, "sage")
    slices = [(PANEL_TOP - 0.28, PANEL_TOP - 0.16, 0.00), (PANEL_TOP - 0.16, PANEL_TOP - 0.08, 0.04),
              (PANEL_TOP - 0.08, PANEL_TOP - 0.04, 0.12), (PANEL_TOP - 0.04, PANEL_TOP, 0.24)]
    for z0, z1, dx in slices:
        g.box(-PANEL_X + dx, yb, z0, PANEL_X - dx, yf, z1, "sage")
    B.part("Wall_Panel", c, g, (0, RY1, 0), tags={"note": "painted accent behind the poster grid"})

    # rug under desk and chair: peach with a terracotta border and a sage line
    rx, ry0, ry1 = 1.0, -0.80, 1.24
    ni, nj = int(round(2 * rx / 0.04)), int(round((ry1 - ry0) / 0.04))
    cells = {}
    for i in range(ni):
        for j in range(nj):
            e = min(i, j, ni - 1 - i, nj - 1 - j)
            m = "terra" if e <= 1 else ("sage" if e == 3 else "peach")
            cells[(i, j, 0)] = m
    g = Geo().vox(cells, (0.04, 0.04, 0.012), (-rx, ry0, 0.0))
    B.part("Rug", c, g, (0, (ry0 + ry1) / 2, 0))

    # tall snake plant in a terracotta pot, front of the floor lamp
    px, py = 1.10, 0.66
    cells = {}
    for k in range(8):
        for i, j in circle(8):
            cells[(i, j, k)] = "terra"
    for i, j in ring(8, 6):
        cells[(i, j, 8)] = "terra"
    for i, j in circle(6):
        cells[(i, j, 7)] = "soil"
    g = Geo().vox(cells, 0.04, (px, py, 0.0))
    blades = [(-0.06, -0.02, 1.02, -0.6, 0.0), (0.03, -0.05, 1.18, 0.2, -0.5), (0.07, 0.03, 0.92, 0.7, 0.2),
              (-0.02, 0.06, 0.86, -0.2, 0.7), (0.0, 0.0, 1.30, 0.0, 0.0), (-0.08, 0.05, 0.74, -0.8, 0.5),
              (0.08, -0.06, 0.70, 0.8, -0.6), (0.04, 0.08, 1.06, 0.3, 0.6), (-0.05, -0.08, 0.96, -0.4, -0.7)]
    pz = 0.32
    for b, (bx, by, hgt, lx, ly) in enumerate(blades):
        n = int(hgt / 0.04)
        for k in range(n):
            t = k / n
            off = 0.10 * t * t                                 # gentle outward lean
            w = 0.06 if t < 0.7 else (0.04 if t < 0.88 else 0.02)
            mat = "succ" if (k // 3 + b) % 2 == 0 else "succ_dark"
            hx, hy = (w / 2, 0.012) if b % 2 == 0 else (0.012, w / 2)   # blades face different ways
            x, y = px + bx + lx * off, py + by + ly * off
            g.box(x - hx, y - hy, pz + k * 0.04, x + hx, y + hy, pz + (k + 1) * 0.04, mat)
    B.part("Floor_Plant", c, g, (px, py, 0.0))


# ================================================================ desk
def build_desk(B):
    c = "Desk"
    z = DESK_SIT
    lift = B.empty("Desk_Lift", c, T(0, 0, z), size=0.25, kind="ARROWS")
    lift["sitting_z"] = DESK_SIT
    lift["standing_z"] = DESK_STAND
    lift["note"] = "animate location.z between sitting_z and standing_z; tabletop surface = lift Z"

    g = Geo()                                                       # wooden top: 6 planks along X + grain
    n, pd = 6, DESK_D / 6
    rnd = random.Random(5)
    for p in range(n):
        y0 = -DESK_D / 2 + p * pd
        g.box(-DESK_W / 2, y0, z - 0.04, DESK_W / 2, y0 + pd, z, "desk" if p % 2 == 0 else "desk2")
        for _ in range(4):
            L = rnd.uniform(0.18, 0.55)
            x0 = rnd.uniform(-DESK_W / 2 + 0.02, DESK_W / 2 - 0.02 - L)
            yy = y0 + rnd.uniform(0.025, pd - 0.025)
            g.box(x0, yy - 0.004, z, x0 + L, yy + 0.004, z + 0.0006, "desk_grain")
    B.part("Desk_Top", c, g, (0, 0, z - 0.04), parent=lift)
    g = Geo()                                                       # black frame under the top
    for sx in (-1, 1):
        g.box(sx * LEG_X - 0.03, -0.30, z - 0.08, sx * LEG_X + 0.03, 0.30, z - 0.04, "leg")
    g.box(-LEG_X, -0.02, z - 0.08, LEG_X, 0.02, z - 0.04, "leg")
    B.part("Desk_Frame", c, g, (0, 0, z - 0.08), parent=lift)
    for side, sx in (("R", -1), ("L", 1)):           # L/R from her point of view (her left = +X)
        x = sx * LEG_X
        B.part("Desk_Leg_%s_Inner" % side, c, Geo().box(x - 0.04, -0.04, z - 0.56, x + 0.04, 0.04, z - 0.08, "leg"),
               (x, 0, z - 0.56), parent=lift)
        g = Geo()
        g.box(x - 0.04, -0.32, 0.0, x + 0.04, 0.32, 0.04, "leg")
        g.box(x - 0.06, -0.06, 0.04, x + 0.06, 0.06, 0.60, "leg")
        B.part("Desk_Leg_%s_Base" % side, c, g, (x, 0, 0), tags={"fixed": True})
    g = Geo()                                                       # control panel, front right under the top
    px, py = -0.52, DESK_D / 2
    g.box(px - 0.06, py - 0.06, z - 0.07, px + 0.06, py - 0.005, z - 0.04, "leg")
    for bx in (-0.035, -0.012):
        g.box(px + bx - 0.008, py - 0.005, z - 0.062, px + bx + 0.008, py - 0.001, z - 0.048, "tech")
    g.box(px + 0.008, py - 0.005, z - 0.062, px + 0.045, py - 0.002, z - 0.048, "white")
    B.part("Desk_Control", c, g, (px, py - 0.03, z - 0.07), parent=lift)
    return lift


# ================================================================ desk items
def build_desk_items(B, lift):
    c = "DeskItems"
    z = DESK_SIT
    screens = {}

    # ---- laptop stand + laptop + screen (centre, facing her: +Y)
    sx, sy = 0.0, -0.08
    O = T(sx, sy, z)
    tilt = 15.0
    Mp = O @ T(0, 0, 0.061) @ Rx(-tilt)
    g = Geo()
    g.obox(Mp, -0.125, -0.12, -0.004, 0.125, 0.12, 0.004, "tech")
    g.obox(Mp, -0.125, 0.108, 0.004, 0.125, 0.12, 0.016, "tech")                       # front lip
    g.box(sx - 0.11, sy - 0.125, z, sx + 0.11, sy - 0.105, z + 0.088, "tech")          # rear leg
    g.box(sx - 0.11, sy + 0.100, z, sx + 0.11, sy + 0.122, z + 0.026, "tech")          # front foot
    stand = B.part("Laptop_Stand", c, g, (sx, sy, z), parent=lift)

    Mb = Mp @ T(0, -0.004 - 0.105 * (LAPTOP_SCALE - 1), 0.004)   # scaled base stays behind the front lip
    g = Geo()
    g.obox(Mb, -0.15, -0.105, 0, 0.15, 0.105, 0.014, "tech")
    g.obox(Mb, -0.13, -0.095, 0.014, 0.13, -0.02, 0.0155, "keys_dark")
    g.obox(Mb, -0.055, 0.0, 0.014, 0.055, 0.085, 0.0152, "tech_light")
    hinge = Mb @ Vector((0, -0.105, 0.014))
    Ml = T(*hinge) @ Rx(12.0)
    g.obox(Ml, -0.15, -0.006, -0.004, 0.15, 0.0, 0.208, "tech")
    g.obox(Ml, -0.146, 0.0, 0.004, 0.146, 0.0008, 0.200, "bezel")
    base_pt = Mb @ Vector((0, 0, 0))
    laptop = B.part("Laptop", c, g, tuple(base_pt), parent=stand)
    sw = 0.272
    screens["Laptop"] = B.plane("Screen_Laptop", c, sw, sw / 1.6, image_material("screen_laptop", SCREEN_EMISSION),
                                Ml @ T(0, 0.0016, 0.102) @ Rz(180), parent=laptop, tags={"texture": "screen_laptop.png"})
    laptop.scale = (LAPTOP_SCALE,) * 3                 # about its base on the stand; the screen follows

    # ---- felt desk mat under keyboard and mouse (sage); keyboard and mouse sit on it
    mat_t = 0.003
    mx0, mx1, my0, my1 = -0.37, 0.21, 0.075, 0.315
    g = Geo().box(mx0, my0, z, mx1, my1, z + mat_t, "sage_dark")
    B.part("Desk_Mat", c, g, ((mx0 + mx1) / 2, (my0 + my1) / 2, z), parent=lift)
    z = DESK_SIT + mat_t

    # ---- keyboard (thin, silver body, white keys)
    kx, ky = 0.0, 0.19
    g = Geo()
    g.box(kx - 0.14, ky - 0.0575, z, kx + 0.14, ky + 0.0575, z + 0.006, "tech")
    g.box(kx - 0.14, ky - 0.0575, z + 0.006, kx + 0.14, ky - 0.047, z + 0.010, "tech")
    p, ks = 0.0188, 0.0158
    rows = [14, 14, 13, 12]
    for r, ncol in enumerate(rows):
        yc = ky - 0.034 + r * p
        x_start = kx - (ncol * p) / 2
        for col in range(ncol):
            x0 = x_start + col * p + (p - ks) / 2
            g.box(x0, yc - ks / 2, z + 0.006, x0 + ks, yc + ks / 2, z + 0.0085, "white")
    yc = ky - 0.034 + 4 * p
    x0 = kx - 7 * p
    for w in (1, 1, 1, 1.3, 5.4, 1.3, 1, 1, 1):
        g.box(x0 + (p - ks) / 2, yc - ks / 2, z + 0.006, x0 + w * p - (p - ks) / 2, yc + ks / 2, z + 0.0085, "white")
        x0 += w * p
    B.part("Keyboard", c, g, (kx, ky, z), parent=lift)

    # ---- sculpted graphite mouse (her right = -X)
    mx, my = -0.25, 0.19
    cells = {}
    for i in range(-2, 1):
        for j in range(-2, 3):
            if not (i in (-2, 0) and j in (-2, 2)):
                cells[(i, j, 0)] = "graphite"
    for i, j in ((-1, -1), (-1, 0), (-1, 1), (-2, 0), (0, 0), (0, -1)):
        cells[(i, j, 1)] = "graphite"
    cells[(-1, 0, 2)] = "graphite"
    g = Geo().vox(cells, (0.02, 0.02, 0.012), (mx + 0.01, my - 0.01, z))
    B.part("Mouse", c, g, (mx, my, z), parent=lift)
    z = DESK_SIT

    # ---- Claude's dock (her right of the laptop): silver puck with a glowing band, anchor on top
    dx, dy = -0.30, -0.10
    cells = {(i, j, 0): "tech" for i, j in circle(9)}
    cells.update({(i, j, 1): "dock_glow" for i, j in ring(9, 7)})
    cells.update({(i, j, 1): "tech" for i, j in circle(7)})
    cells.update({(i, j, 2): "tech" for i, j in circle(7)})
    cells.update({(i, j, 3): "white" for i, j in circle(5)})
    dock_h = 0.012 * 3 + 0.004
    g = Geo().vox({k: v for k, v in cells.items() if k[2] < 3}, (0.02, 0.02, 0.012), (dx - 0.01, dy - 0.01, z))
    g.vox({(i, j, 0): "white" for i, j in circle(5)}, (0.02, 0.02, 0.004), (dx - 0.01, dy - 0.01, z + 0.036))
    dock = B.part("Claude_Dock", c, g, (dx, dy, z), parent=lift, tags={"glow_material": PREFIX + "dock_glow"})
    B.empty("Claude_Dock_Anchor", c, T(dx, dy, z + dock_h), parent=dock, size=0.08, kind="SINGLE_ARROW")

    # ---- phone on a wireless charger (far right)
    phx, phy = -0.58, -0.12
    g = Geo().vox({(i, j, 0): "white" for i, j in circle(9)}, (0.01, 0.01, 0.006), (phx - 0.005, phy - 0.005, z))
    charger = B.part("Phone_Charger", c, g, (phx, phy, z), parent=lift)
    pz = z + 0.006
    g = Geo()
    g.box(phx - 0.036, phy - 0.068, pz, phx + 0.036, phy + 0.068, pz + 0.008, "tech")
    g.box(phx - 0.030, phy - 0.074, pz, phx + 0.030, phy + 0.074, pz + 0.008, "tech")
    g.box(phx - 0.034, phy - 0.071, pz + 0.008, phx + 0.034, phy + 0.071, pz + 0.0085, "bezel")
    phone = B.part("Phone", c, g, (phx, phy, pz), parent=charger)
    pw = 0.062
    screens["Phone"] = B.plane("Screen_Phone", c, pw, pw * 1950 / 900, image_material("screen_phone", SCREEN_EMISSION),
                               T(phx, phy, pz + 0.0092) @ Rz(180) @ Rx(-90), parent=phone,
                               tags={"texture": "screen_focus_phone.png"})

    # ---- tablet on a stand + stylus (her left = +X), screen shows Focus mode
    tx, ty = 0.42, -0.08
    g = Geo()
    g.box(tx - 0.07, ty - 0.06, z, tx + 0.07, ty + 0.05, z + 0.008, "tech")
    g.box(tx - 0.07, ty + 0.034, z + 0.008, tx + 0.07, ty + 0.05, z + 0.022, "tech")
    Mt = T(tx, ty + 0.034, z + 0.010) @ Rx(20.0)
    g.obox(Mt, -0.05, -0.017, 0.0, 0.05, -0.007, 0.14, "tech")
    tstand = B.part("Tablet_Stand", c, g, (tx, ty, z), parent=lift)
    g = Geo()
    g.obox(Mt, -0.09, -0.007, 0.0, 0.09, 0.0, 0.25, "tech")
    g.obox(Mt, -0.087, 0.0, 0.003, 0.087, 0.0008, 0.247, "bezel")
    tablet = B.part("Tablet", c, g, tuple(Mt @ Vector((0, 0, 0))), parent=tstand)
    tw = 0.165
    screens["Tablet"] = B.plane("Screen_Tablet", c, tw, tw * 1600 / 1200, image_material("screen_tablet", SCREEN_EMISSION),
                                Mt @ T(0, 0.0016, 0.125) @ Rz(180), parent=tablet,
                                tags={"texture": "screen_focus_tablet.png"})
    stx, sty = tx, ty + 0.10
    g = Geo()
    g.box(stx - 0.075, sty - 0.0045, z, stx + 0.075, sty + 0.0045, z + 0.009, "white")
    g.box(stx + 0.075, sty - 0.003, z + 0.0015, stx + 0.085, sty + 0.003, z + 0.0075, "tech")
    B.part("Stylus", c, g, (stx, sty, z), parent=lift)

    # ---- green tea in a cobalt ceramic cup + steam wisp
    cx, cy = 0.60, 0.14
    cup_m = "cobalt"
    cells = {}
    for k in range(4):
        for i, j in circle(4):
            inner = (i, j) in circle(2)
            if k == 0 or not inner:
                cells[(i, j, k)] = cup_m
            elif k == 2:
                cells[(i, j, k)] = "tea"
    hcells = {(0, 0, 2): cup_m, (0, 0, 6): cup_m, (1, 0, 2): cup_m, (1, 0, 6): cup_m,
              (2, 0, 3): cup_m, (2, 0, 4): cup_m, (2, 0, 5): cup_m}     # C-shaped handle, finer grid
    g = Geo().vox(cells, (0.02, 0.02, 0.022), (cx, cy, z))
    g.vox(hcells, (0.01, 0.012, 0.011), (cx + 0.04, cy - 0.006, z))
    cup = B.part("Tea_Cup", c, g, (cx, cy, z), parent=lift)
    wisp = [(0, 0, 0), (0, 0, 1), (1, 0, 2), (1, 0, 3), (0, 0, 4), (-1, 0, 5), (-1, 0, 6), (0, 0, 7), (0, 0, 8)]
    g = Geo().vox({p: "steam" for p in wisp}, (0.012, 0.012, 0.014), (cx - 0.006, cy - 0.006, z + 0.09))
    B.part("Tea_Steam", c, g, (cx, cy, z + 0.09), parent=cup)

    # ---- small succulent in a white pot (back left corner)
    B.part("Succulent_Desk", c, succulent_geo(0.62, -0.24, z, 1), (0.62, -0.24, z), parent=lift)
    return screens


def succulent_geo(x, y, z, size):
    """White pot 0.08 wide, plant rosettes; size 1..3 makes the plant taller."""
    cells = {}
    for k in range(3):
        for i, j in circle(4):
            cells[(i, j, k)] = "white"
    for i, j in circle(2):
        cells[(i, j, 2)] = "soil"
    leaves = {}
    if size == 1:
        for i, j in circle(4):
            leaves[(i, j, 3)] = "succ_dark"
        for i, j in ((-2, 0), (1, -1), (0, 1), (-1, -2)):
            leaves[(i, j, 3)] = "succ"
        for i, j in circle(2):
            leaves[(i, j, 4)] = "succ"
    elif size == 2:
        for i, j in circle(6):
            if abs(i + 0.5) + abs(j + 0.5) <= 3:
                leaves[(i, j, 3)] = "succ_dark"
        for i, j in circle(4):
            leaves[(i, j, 4)] = "succ"
        for i, j in circle(2):
            leaves[(i, j, 5)] = "succ"
    else:
        for i, j in circle(4):
            leaves[(i, j, 3)] = "succ_dark"
        for k in range(4, 9):
            for i, j in circle(2):
                leaves[(i, j, k)] = "succ" if k % 2 == 0 else "succ_dark"
        for i, j, k in ((-2, 0, 5), (1, -1, 6), (-2, -1, 7), (1, 0, 4)):
            leaves[(i, j, k)] = "succ"
    cells.update(leaves)
    return Geo().vox(cells, (0.02, 0.02, 0.02), (x, y, z))


# ================================================================ shelf + items
SHELF_X = (-1.58, -1.00)
SHELF_Y = (RY1 - 0.24, RY1)
SHELF_Z = [0.80, 1.20, 1.60, 2.00]     # top surfaces of the planks


def build_shelf(B):
    g = Geo()
    (x0, x1), (y0, y1) = SHELF_X, SHELF_Y
    for zt in SHELF_Z:
        g.box(x0, y0, zt - 0.02, x1, y1, zt, "wood")
    for xa in (x0 - 0.02, x1):
        for ya in (y0, y1 - 0.02):
            g.box(xa, ya, SHELF_Z[0] - 0.10, xa + 0.02, ya + 0.02, SHELF_Z[-1] + 0.12, "frame")
        for zt in SHELF_Z:
            g.box(xa, y0, zt - 0.04, xa + 0.02, y1, zt - 0.02, "frame")
    B.part("Shelf", "Shelf", g, ((x0 + x1) / 2, y1, SHELF_Z[0] - 0.10))


AMPERSAND = [
    "...XXXX....",
    "..XXXXXX...",
    "..XX..XX...",
    "..XX..XX...",
    "..XXXXX....",
    "...XXX.....",
    "..XXXXX..XX",
    ".XX..XXX.XX",
    "XX....XXXX.",
    "XX.....XX..",
    "XX....XXXX.",
    ".XXXXXXX.XX",
    "..XXXX....X",
]


def build_shelf_items(B):
    c = "ShelfItems"
    xa, xb = SHELF_X[0] + 0.15, SHELF_X[1] - 0.15
    yc = (SHELF_Y[0] + SHELF_Y[1]) / 2
    z1, z2, z3, z4 = SHELF_Z

    # ---- shelf 1: three succulents lined up by height, palo santo with smoke
    for n, x in enumerate((xa - 0.09, xa + 0.01, xa + 0.11)):
        B.part("Succulent_Shelf_%d" % (n + 1), c, succulent_geo(x, yc, z1, n + 1), (x, yc, z1))
    px = xb + 0.02
    cells = {(i, j, 0): "ceramic" for i, j in circle(6)}
    cells.update({(i, j, 1): "ceramic" for i, j in ring(6, 4)})
    g = Geo().vox(cells, (0.02, 0.02, 0.012), (px, yc, z1))
    dish = B.part("PaloSanto_Dish", c, g, (px, yc, z1))
    g = Geo()
    g.box(px - 0.05, yc - 0.008, z1 + 0.012, px + 0.035, yc + 0.008, z1 + 0.028, "palo")
    g.box(px + 0.035, yc - 0.008, z1 + 0.012, px + 0.05, yc + 0.008, z1 + 0.028, "palo_burnt")
    stick = B.part("PaloSanto_Stick", c, g, (px, yc, z1 + 0.012), parent=dish)
    wisp = [(0, 0, 0), (0, 0, 1), (-1, 0, 2), (-1, 0, 3), (0, 0, 4), (1, 0, 5), (1, 0, 6), (0, 0, 7),
            (0, 0, 8), (-1, 0, 9), (-1, 0, 10)]
    g = Geo().vox({p: "smoke" for p in wisp}, (0.01, 0.01, 0.014), (px + 0.04, yc - 0.005, z1 + 0.03))
    B.part("PaloSanto_Smoke", c, g, (px + 0.045, yc, z1 + 0.03), parent=stick)

    # ---- shelf 2: juicer (white body, clear dome), buddha
    jx = xa
    cells = {}
    for k in range(5):
        for i, j in circle(8):
            cells[(i, j, k)] = "white"
    for i, j in ring(8, 6):
        cells[(i, j, 5)] = "white"
    for i, j in circle(6):
        cells[(i, j, 4)] = "white"
    for i, j in circle(4):
        cells[(i, j, 5)] = "white"
    for i, j in circle(2):
        cells[(i, j, 6)] = "white"
        cells[(i, j, 7)] = "white"
    cells[(-1, -5, 4)] = "white"            # spout at the front
    cells[(0, -5, 4)] = "white"
    for i, j in ring(8, 6):
        cells[(i, j, 6)] = "glass"
        cells[(i, j, 7)] = "glass"
    for i, j in ring(6, 4):
        cells[(i, j, 8)] = "glass"
    for i, j in circle(4):
        cells[(i, j, 9)] = "glass"
    g = Geo().vox(cells, (0.02, 0.02, 0.022), (jx, yc, z2))
    B.part("Juicer", c, g, (jx, yc, z2), tags={"note": "generic 1970s citrus juicer, no marks"})

    bx = xb
    cells = {}
    for i in range(-3, 3):
        for j in range(-2, 2):
            if not (i in (-3, 2) and j in (-2, 1)):
                cells[(i, j, 0)] = "white"
    for i in range(-3, 3):
        for j in range(-2, 1):
            cells[(i, j, 1)] = "white"
    for k in (2, 3, 4):
        for i in range(-2, 2):
            for j in range(-1, 1):
                cells[(i, j, k)] = "white"
    for i in (-3, 2):
        cells[(i, -1, 2)] = "white"                         # arms / hands in the lap
        cells[(i, -1, 3)] = "white"
    cells[(-1, -1, 5)] = cells[(0, -1, 5)] = "white"        # neck
    for k in (6, 7):
        for i in range(-2, 2):
            for j in range(-2, 1):
                if not (i in (-2, 1) and j in (-2, 0) and k == 7):
                    cells[(i, j, k)] = "white"
    for i in (-3, 2):
        cells[(i, -1, 6)] = "white"                         # ear lobes
    cells[(-1, -1, 8)] = cells[(0, -1, 8)] = "white"        # topknot
    for i in range(-2, 2):
        for j in range(-1, 1):
            cells[(i, j, 5)] = "white"
    g = Geo().vox(cells, (0.02, 0.02, 0.02), (bx, yc, z2))
    B.part("Buddha", c, g, (bx, yc, z2))

    # three upright books between juicer and buddha (spines face the room)
    g = Geo()
    x = -1.338
    y0, y1 = yc - 0.08, yc + 0.08
    for t, hgt, m in ((0.032, 0.22, "terra"), (0.028, 0.25, "sage_dark"), (0.036, 0.20, "cobalt")):
        g.box(x, y0, z2, x + t, y1, z2 + hgt, m)
        g.box(x + 0.004, y0 - 0.001, z2 + hgt - 0.05, x + t - 0.004, y0, z2 + hgt - 0.035, "paper")
        x += t + 0.002
    B.part("Books_Shelf", c, g, ((-1.338 + x) / 2, yc, z2))

    # ---- shelf 3: empty pedestal with plaque, pink basketball on a stand
    pdx = xa
    g = Geo()
    g.box(pdx - 0.06, yc - 0.06, z3, pdx + 0.06, yc + 0.06, z3 + 0.20, "white")
    g.box(pdx - 0.07, yc - 0.07, z3 + 0.20, pdx + 0.07, yc + 0.07, z3 + 0.22, "white")
    g.box(pdx - 0.07, yc - 0.07, z3, pdx + 0.07, yc + 0.07, z3 + 0.02, "white")
    ped = B.part("Pedestal", c, g, (pdx, yc, z3))
    pw = 0.11
    B.plane("Plaque", c, pw, pw / 4, image_material("plaque"), T(pdx, yc - 0.0615, z3 + 0.12), parent=ped,
            tags={"texture": "plaque_awwwards.png"})

    bbx = xb
    g = Geo()
    g.box(bbx - 0.06, yc - 0.06, z3, bbx + 0.06, yc + 0.06, z3 + 0.04, "frame")
    g.vox({(i, j, 0): "frame" for i, j in ring(6, 4)}, (0.02, 0.02, 0.02), (bbx, yc, z3 + 0.04))
    stand = B.part("Basketball_Stand", c, g, (bbx, yc, z3))
    cells = {}
    n = 11
    r = n / 2.0
    for i in range(n):
        for j in range(n):
            for k in range(n):
                dx, dy, dz = i + 0.5 - r, j + 0.5 - r, k + 0.5 - r
                if dx * dx + dy * dy + dz * dz <= r * r - 0.3:
                    seam = abs(dx) < 0.55 or abs(dz) < 0.55 or (abs(dy) < 0.55 and abs(dx) > 2.5)
                    cells[(i - 5, j - 5, k)] = "ball_seam" if seam else "ball"
    g = Geo().vox(cells, 0.02, (bbx - 0.01, yc - 0.01, z3 + 0.05))
    B.part("Basketball", c, g, (bbx, yc, z3 + 0.05), parent=stand)

    # ---- shelf 4: ampersand art object, framed "Featured" ribbon
    cells = {}
    rows = len(AMPERSAND)
    for r_, row in enumerate(AMPERSAND):
        for col, ch in enumerate(row):
            if ch == "X":
                for j in (0, 1):
                    cells[(col - 6, j, rows - 1 - r_)] = "frame"   # 11 wide: x -6..4
    g = Geo().vox(cells, 0.02, (xa, yc - 0.01, z4))
    B.part("Ampersand", c, g, (xa, yc, z4))

    fx, fy = xb, SHELF_Y[1] - 0.04
    iw, ih, b = 0.16, 0.20, 0.02
    g = Geo()
    g.box(fx - iw / 2 - b, fy - 0.02, z4, fx + iw / 2 + b, fy, z4 + b, "frame")
    g.box(fx - iw / 2 - b, fy - 0.02, z4 + b + ih, fx + iw / 2 + b, fy, z4 + 2 * b + ih, "frame")
    g.box(fx - iw / 2 - b, fy - 0.02, z4 + b, fx - iw / 2, fy, z4 + b + ih, "frame")
    g.box(fx + iw / 2, fy - 0.02, z4 + b, fx + iw / 2 + b, fy, z4 + b + ih, "frame")
    g.box(fx - iw / 2, fy - 0.005, z4 + b, fx + iw / 2, fy, z4 + b + ih, "frame")
    g.box(fx - 0.03, fy, z4, fx + 0.03, fy + 0.03, z4 + 0.10, "frame")                 # back strut
    rf = B.part("Ribbon_Frame", c, g, (fx, fy, z4))
    B.plane("Ribbon_Image", c, iw, ih, image_material("ribbon_img"), T(fx, fy - 0.006, z4 + b + ih / 2), parent=rf,
            tags={"texture": "ribbon_featured.png"})


# ================================================================ posters
POSTER_W, POSTER_H, FRAME_B = 0.44, 0.66, 0.02
POSTERS = [  # (name, texture key, column, row, tilt deg) - row 0 = top
    ("Eyechart", "poster_eyechart", -1, 0, 2.0),
    ("Lorem", "poster_lorem", 0, 0, 0.0),
    ("Chtoby", "poster_chtoby", 1, 0, 0.0),
    ("Kerning", "poster_kerning", -1, 1, 0.0),
    ("Rams", "poster_rams", 1, 1, 0.0),
]
POSTER_FRAME = {"Chtoby": "frame_pink"}   # frame palette key per poster; default "frame" (black)
POSTER_COL = 0.60
POSTER_ROW_Z = [2.19, 1.37]


def build_posters(B):
    c = "Posters"
    w, h, b = POSTER_W, POSTER_H, FRAME_B
    yw = RY1
    for name, key, col, row, tilt in POSTERS:
        x, zc = col * POSTER_COL, POSTER_ROW_Z[row]
        M = T(x, yw - 0.02, zc) @ Matrix.Rotation(math.radians(tilt), 4, "Y")
        poster = B.plane("Poster_" + name, c, w, h, image_material(key), M,
                         tags={"texture": TEXTURES[key][0], "grid": "col %d row %d" % (col, row)})
        fk = POSTER_FRAME.get(name, "frame")
        g = Geo()
        d0, d1 = -0.015, 0.02          # frame depth in poster space (wall at +0.02)
        g.box(-w / 2 - b, d0, -h / 2 - b, w / 2 + b, d1, -h / 2, fk)
        g.box(-w / 2 - b, d0, h / 2, w / 2 + b, d1, h / 2 + b, fk)
        g.box(-w / 2 - b, d0, -h / 2, -w / 2, d1, h / 2, fk)
        g.box(w / 2, d0, -h / 2, w / 2 + b, d1, h / 2, fk)
        g.box(-w / 2, 0.004, -h / 2, w / 2, d1, h / 2, fk)          # backing board
        B.part("Poster_%s_Frame" % name, c, g, parent=poster, M=M)       # built in the poster's local space


# ================================================================ lights, world, cameras
def build_lights(B):
    sc = B.scene
    w = bpy.data.worlds.new(PREFIX + "World")
    try:
        w.use_nodes = True
    except Exception:
        pass
    bg = next((n for n in w.node_tree.nodes if n.type == "BACKGROUND"), None)
    if bg:
        bg.inputs[0].default_value = hex_rgba("#EEF0F2")
        bg.inputs[1].default_value = 0.06
    sc.world = w

    # ---- day: soft window light from the left (her right)
    d = "Lights_Day"
    (wy0, wy1), (wz0, wz1) = WIN_Y, WIN_Z
    ym, zm = (wy0 + wy1) / 2, (wz0 + wz1) / 2
    # one soft key from the window (area light filling the opening), a soft sun through it for the
    # directional falloff, and a minimum of shadowless fill so the shaded side does not go muddy
    B.light("Window_Soft", d, "AREA", DAY["window_area"], DAY["window_color"],
            aim((RX0 + 0.40, ym, zm + 0.06), (1, 0.4, -0.4)), shape="RECTANGLE", size=wy1 - wy0 - 0.22,
            size_y=wz1 - wz0 - 0.26, spread=math.radians(70))   # 0.4 m inside: no hot spots on sill / reveals
    B.light("Sun_Window", d, "SUN", DAY["window_sun"], DAY["sun_color"], aim((RX0 - 1, ym, zm + 1), (0.80, 0.30, -0.52)),
            angle=math.radians(25))
    B.light("Day_Fill", d, "SUN", DAY["fill"], "#F1EFEC", aim((0.0, -2.5, 2.4), (0.12, 0.80, -0.59)), angle=0.5,
            use_shadow=False)
    B.light("Day_Sky", d, "SUN", DAY["sky"], "#ECEEF2", aim((0.0, 0.0, 2.6), (0.0, 0.0, 1.0)), angle=0.5,
            use_shadow=False)      # stands in for floor bounce: keeps the ceiling from going black
    B.light("Day_Bounce", d, "SUN", DAY["bounce"], "#F3EEE8", aim((0.0, 0.0, 2.0), (-0.8, -0.45, -0.3)), angle=0.6,
            use_shadow=False)      # light bounced back off the sunlit right wall: the room's back-facing sides
    wb = B.light("Day_Bounce_Walls", d, "SUN", DAY["wall_bounce"], "#F3EEE8", aim((0.0, 0.0, 2.2), (-0.85, -0.4, -0.2)),
                 angle=0.6, use_shadow=False)
    # these two are light-linked to the walls only (window + front wall, and the right wall), which otherwise
    # face away from every day light
    # (EEVEE light linking; three.js will need its own equivalent, e.g. a weak fill on those walls)
    ws = B.light("Day_Wall_Spill", d, "SUN", DAY["wall_spill"], DAY["window_color"], aim((0.0, 0.0, 2.2), (1.0, 0.25, -0.3)),
                 angle=0.6, use_shadow=False)       # window light spilling onto the opposite (right) wall
    for lt, walls in ((wb, ("Wall_Left", "Wall_Front")), (ws, ("Wall_Right",))):
        rc = bpy.data.collections.new(PREFIX + "LL_" + lt.name[len(PREFIX):])
        for n in walls:
            rc.objects.link(bpy.data.objects[PREFIX + n])
        try:
            lt.light_linking.receiver_collection = rc
        except Exception as exc:
            print("light linking unavailable:", exc)

    # ---- evening: screens glow (the lamp collection is switched on with it by set_lighting)
    e = "Lights_Evening"
    B.light("Glow_Laptop", e, "SPOT", 6.0, "#E6EEFF", aim((0, -0.10, DESK_SIT + 0.22), (0, 1, 0.05)),
            spot_size=math.radians(120), spot_blend=1.0, shadow_soft_size=0.12)
    B.light("Glow_Tablet", e, "SPOT", 2.0, "#E6EEFF", aim((0.42, -0.04, DESK_SIT + 0.14), (0, 1, 0.1)),
            spot_size=math.radians(110), spot_blend=1.0, shadow_soft_size=0.08)
    B.light("Glow_Dock", e, "POINT", 0.6, PALETTE["dock_glow"], T(-0.30, -0.10, DESK_SIT + 0.14), shadow_soft_size=0.05)
    B.light("Evening_Fill", e, "SUN", 0.07, "#8C96C8", aim((0.0, -2.5, 2.4), (0.1, 1.0, -0.5)), angle=0.6, use_shadow=False)

    # ---- lamp: colour gradient wash (A = warm start at the lamp, B = cool end over the ceiling)
    l = "Lights_Lamp"
    lx, ly = LAMP_XY
    head = (lx, ly, LAMP_HEAD_Z + 0.08)
    # A: tight-ish warm cone into the corner; B: wide cool cone up across the ceiling
    B.light("Lamp_Light_A", l, "SPOT", 80.0, LAMP_A, aim(head, (0.25, 0.3, 1)),
            spot_size=math.radians(80), spot_blend=1.0, shadow_soft_size=0.06)
    B.light("Lamp_Light_B", l, "SPOT", 200.0, LAMP_B, aim(head, (-0.75, -0.6, 1)),
            spot_size=math.radians(110), spot_blend=1.0, shadow_soft_size=0.06)

    for name, hide in (("Lights_Evening", True),):
        col = B.colls[name]
        col.hide_render = hide
        col.hide_viewport = hide


# ================================================================ city outside the window
def build_exterior(B):
    """Voxel city: three rows of buildings at different distances (parallax), stepped-gradient sky,
    street ground. All self-lit and shadowless, so it never blocks or alters the window light."""
    c = "Exterior"

    def emat(key, day, eve):
        if key not in B.mats:
            B.mats[key] = ext_material(key, day, eve)
        return key

    obs = []
    # sky: one big wall of horizontal bands facing the room
    g = Geo()
    for n, (z0, z1, day, eve) in enumerate(SKY_BANDS):
        g.box(SKY_X - 0.5, -90, z0, SKY_X, 90, z1, emat("ext_sky_%d" % n, day, eve))
    obs.append(B.part("City_Sky", c, g, (SKY_X, 0, GROUND_Z)))
    g = Geo().box(SKY_X, -90, GROUND_Z - 0.5, RX0 - 2.0, 90, GROUND_Z, emat("ext_ground", *CITY_GROUND))
    obs.append(B.part("City_Ground", c, g, (-20, 0, GROUND_Z)))

    rnd = random.Random(2024)
    for name, fx, (ya, yb), (wa, wb), (da, db), (ha, hb), (px, pz), cols in CITY_ROWS:
        wday, wlit, wdark = CITY_WIN[name]
        k_lit = emat("ext_%s_win_lit" % name.lower(), wday, wlit)
        k_dark = emat("ext_%s_win_dark" % name.lower(), wday, wdark)
        keys = []
        for n, (day, eve) in enumerate(cols):
            base = "ext_%s_%d" % (name.lower(), n)
            keys.append((emat(base, day, eve),                                             # facade + roof
                         emat(base + "_side", shade_hex(day, 0.86), shade_hex(eve, 0.80))))
        g = Geo()
        y = ya + rnd.uniform(0, 1.5)
        while y < yb:
            w = rnd.uniform(wa, wb)
            d = rnd.uniform(da, db)
            top = rnd.uniform(ha, hb)
            x1 = fx - rnd.uniform(0, 0.8)                     # facades not perfectly in line
            fk, sk = keys[rnd.randrange(len(keys))]
            g.box6(x1 - d, y, GROUND_Z, x1, y + w, top, fk, side=sk, top=fk)
            if rnd.random() < 0.4:                            # rooftop box (stair / tank)
                rw = rnd.uniform(0.6, 1.4)
                ry = y + rnd.uniform(0.2, max(0.3, w - rw - 0.2))
                g.box6(x1 - d * 0.6, ry, top, x1 - d * 0.6 + rw, ry + rw, top + rnd.uniform(0.5, 1.1), fk, side=sk)
            # window grid on the facade facing the room
            ncol = max(1, int((w - 0.5) / px))
            margin = (w - ncol * px) / 2
            zc = GROUND_Z + 1.6
            while zc + 0.8 < top:
                if zc > -6.0:
                    for i in range(ncol):
                        wy = y + margin + i * px + px * 0.22
                        k = k_lit if rnd.random() < CITY_LIT else k_dark
                        g.box(x1, wy, zc, x1 + 0.06, wy + px * 0.56, zc + pz * 0.6, k)
                zc += pz
            y += w + rnd.uniform(0.2, 1.2)
        obs.append(B.part("City_" + name, c, g, (fx, 0, GROUND_Z)))
    for ob in obs:
        ob.visible_shadow = False          # never block the sun / window light
        ob["note"] = "self-lit exterior; set_lighting switches material colours (day_color / evening_color)"


CAMERAS = {  # name: (location, target, lens mm)
    "Cam_Wide": ((0.0, -2.75, 1.30), (0.0, 1.6, 1.42), 26.0),
    "Cam_Medium": ((0.12, -1.30, 1.24), (0.0, 0.55, 1.12), 32.0),
    "Cam_LaptopCU": ((0.02, 0.32, 1.00), (0.0, -0.14, 0.93), 45.0),
    "Cam_KeyboardCU": ((0.32, -0.10, 1.02), (-0.03, 0.20, 0.74), 35.0),
    "Cam_OverShoulder": ((-0.80, 1.05, 1.45), (-0.02, -0.12, 0.93), 50.0),
}


def build_cameras(B):
    sc = B.scene
    for name, (loc, tgt, lens) in CAMERAS.items():
        cd = bpy.data.cameras.new(PREFIX + name)
        cd.lens = lens
        cd.sensor_fit = "AUTO"
        cd.sensor_width = 36.0
        cd.clip_start = 0.01
        cd.clip_end = 30.0
        ob = bpy.data.objects.new(PREFIX + name, cd)
        B._link(ob, "Cameras", look_at(loc, tgt), None)
        ob["target"] = list(tgt)
    sc.camera = bpy.data.objects[PREFIX + "Cam_Wide"]
    sc.render.resolution_x, sc.render.resolution_y = 1080, 1920
    sc.render.resolution_percentage = 100
    try:
        sc.render.engine = "BLENDER_EEVEE"
    except TypeError:
        pass
    for attr, val in (("view_transform", "Standard"), ("look", "None")):
        try:
            setattr(sc.view_settings, attr, val)
        except Exception:
            pass
    for attr, val in (("use_fast_gi", True), ("fast_gi_distance", 0.4), ("use_shadows", True),
                      ("use_raytracing", False), ("taa_render_samples", 32), ("shadow_ray_count", 2)):
        try:
            setattr(sc.eevee, attr, val)
        except Exception:
            pass


# ================================================================ build
def build():
    B = Builder()
    for name in ("Room", "Decor", "Desk", "DeskItems", "Shelf", "ShelfItems", "Posters", "Exterior", "Lights_Day",
                 "Lights_Evening", "Lights_Lamp", "Cameras", "Anchors"):
        B.coll(name)
    build_room(B)
    build_decor(B)
    build_exterior(B)
    lift = build_desk(B)
    build_desk_items(B, lift)
    build_shelf(B)
    build_shelf_items(B)
    build_posters(B)
    build_lights(B)
    build_cameras(B)
    a = B.empty("Character_Anchor", "Anchors", T(0, 0.64, 0), size=0.3, kind="SINGLE_ARROW")
    a["facing"] = "-Y (towards the desk and Cam_Medium)"
    a["seat_z"] = 0.44
    a["note"] = "place the Designer root here; sitting: drop hips onto STU_Chair_Seat (seat top 0.44), standing: as is"
    seat_designer()
    set_lighting("day")
    return B


# ================================================================ runtime helpers (usable after build)
def _sc():
    return bpy.data.scenes[SCENE]


def set_desk(pos="sitting"):
    lift = bpy.data.objects[PREFIX + "Desk_Lift"]
    lift.location.z = lift["standing_z"] if pos == "standing" else lift["sitting_z"]


def set_lighting(mode="day"):
    """day: window lights on, lamp OFF (lights hidden, glow materials not emitting);
    evening: screen glow + lamp ON. One call switches everything."""
    day = mode == "day"
    for name, hide in (("Lights_Day", not day), ("Lights_Evening", day), ("Lights_Lamp", day)):
        c = bpy.data.collections[PREFIX + name]
        c.hide_render = hide
        c.hide_viewport = hide
    for key in ("lamp_glow", "lamp_glow_B"):
        m = bpy.data.materials.get(PREFIX + key)
        if m:
            bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
            bsdf.inputs["Emission Strength"].default_value = 0.0 if day else EMISSION[key]
    for m in bpy.data.materials:                     # city: sky, buildings, lit / dark windows
        if m.name.startswith(PREFIX) and m.get("exterior"):
            col = hex_rgba(m["day_color"] if day else m["evening_color"])
            bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
            bsdf.inputs["Emission Color"].default_value = col
            m.diffuse_color = col
    lamp = bpy.data.objects.get(PREFIX + "Floor_Lamp")
    if lamp:
        lamp["lamp_on"] = not day
    _sc()["lighting"] = "day" if day else "evening"


def set_lamp(a=LAMP_A, b=LAMP_B):
    ca, cb = hex_rgba(a), hex_rgba(b)
    bpy.data.objects[PREFIX + "Lamp_Light_A"].data.color = ca[:3]
    bpy.data.objects[PREFIX + "Lamp_Light_B"].data.color = cb[:3]
    for key, col in (("lamp_glow", ca), ("lamp_glow_B", cb)):
        m = bpy.data.materials.get(PREFIX + key)
        if m:
            bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
            bsdf.inputs["Base Color"].default_value = col
            bsdf.inputs["Emission Color"].default_value = col
            m.diffuse_color = col


def render_cam(cam, path, res=(540, 960), samples=16):
    sc = _sc()
    old = (sc.camera, sc.render.resolution_x, sc.render.resolution_y, sc.render.filepath)
    sc.camera = bpy.data.objects[PREFIX + cam]
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.image_settings.file_format = "PNG"
    try:
        sc.eevee.taa_render_samples = samples
    except Exception:
        pass
    sc.render.filepath = path
    try:
        bpy.ops.render.render(write_still=True, scene=SCENE)
    finally:
        sc.camera, sc.render.resolution_x, sc.render.resolution_y, sc.render.filepath = old
    return path


def save_blend(path=BLEND_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.data.libraries.write(path, {_sc()}, fake_user=True, path_remap="RELATIVE_ALL")
    return path


def stand_in(on=True, dz=0.0):
    """Temporary scale check: instance the Designer's collection at the character anchor (never saved)."""
    name = PREFIX + "TMP_Designer"
    old = bpy.data.objects.get(name)
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    if not on:
        return None
    src = bpy.data.collections.get("DSG_Character")
    if src is None:
        return None
    ob = bpy.data.objects.new(name, None)
    ob.instance_type = "COLLECTION"
    ob.instance_collection = src
    a = bpy.data.objects[PREFIX + "Character_Anchor"]
    ob.location = a.location + Vector((0, 0, dz))
    _sc().collection.objects.link(ob)
    return ob


# ---- the Designer, seated in the chair (a posed copy of the Designer scene's character)
SEAT_HIP_Y = 0.60     # hip joints: forward on the seat so the knees clear its front edge (y 0.42)
                      # and her belly clears the desk edge (y 0.36)
SEAT_SINK = 0.01      # thighs sink this far into the cushion
THIGH_HALF = 2.5 * S  # half thickness of her thigh (designer.py: 5 voxels)
# per hand, relative to the desktop (x, y, z above desk): wrist and fingertip (bone axis; palm is 0.04 below)
SEAT_HANDS = {".L": ((0.08, 0.32, 0.10), (0.05, 0.19, 0.055)),   # her left hand on the keyboard
              ".R": ((-0.24, 0.33, 0.12), (-0.25, 0.20, 0.080))}  # her right hand on the mouse
SEAT_HEAD_TILT = 8.0  # degrees, looking down at the laptop
DESIGNER_GLOW = 0.2   # in the studio her (opaque) materials also emit their own colour at this strength,
                      # so she reads brighter than the room; on her own material copies, Designer scene untouched


def designer_pose_bases(arm, hands=None, torso=(0.0, 0.0), head=(SEAT_HEAD_TILT, 0.0)):
    """matrix_basis per bone for the seated Designer (armature already placed on the seat).
    hands: {".L"/".R": ((wrist x, y, z), (fingertip x, y, z))}, x/y world, z above the desktop
    (default SEAT_HANDS); torso, head: (pitch down/forward, yaw to her left) in degrees, head in
    world terms. Arms are solved (two-bone IK) from wherever the torso puts the shoulders."""
    hands = hands or SEAT_HANDS
    desk_z = bpy.data.objects[PREFIX + "Desk_Lift"].location.z
    to_arm = arm.matrix_world.inverted()
    bones = arm.data.bones
    pose = {}

    def turn(pitch, yaw):
        return Matrix.Rotation(math.radians(yaw), 3, "Z") @ Matrix.Rotation(math.radians(pitch), 3, "X")

    def place(name, direction=None, rot=None):
        """Pose matrix (armature space): rest twist, Y axis turned onto `direction` (or rotated by rot)."""
        b = bones[name]
        rest = b.matrix_local
        if b.parent is None:
            head_pt = rest.translation
        else:                                       # follow the parent's pose
            p = b.parent
            head_pt = (pose[p.name] @ p.matrix_local.inverted() @ rest).translation
        R = rest.to_3x3()
        if rot is not None:
            R = rot @ R
        elif direction is not None:
            R = (R.col[1].normalized().rotation_difference(Vector(direction).normalized())).to_matrix() @ R
        M = R.to_4x4()
        M.translation = head_pt
        pose[name] = M
        return M

    def tail(name):
        return pose[name] @ Vector((0, bones[name].length, 0))

    def two_bone(s_head, target, l1, l2, pole):
        d = target - s_head
        dist = min(d.length, l1 + l2 - 1e-4)
        u = d.normalized()
        a = (l1 * l1 - l2 * l2 + dist * dist) / (2 * dist)
        h = math.sqrt(max(l1 * l1 - a * a, 0))
        v = (Vector(pole) - Vector(pole).dot(u) * u).normalized()
        return s_head + u * a + v * h

    place("root")
    place("hips")
    place("torso", rot=turn(*torso))
    place("head", rot=turn(*head))
    for s, sx in ((".L", 1), (".R", -1)):
        place("thigh" + s, (0, -1, 0))             # thighs level, forward on the seat
        place("shin" + s, (0, 0, -1))              # shins straight down
        place("foot" + s)                          # feet keep their rest angle
        wrist_w, tip_w = (Vector((x, y, desk_z + z)) for x, y, z in hands[s])
        wrist, tip = to_arm @ wrist_w, to_arm @ tip_w
        sh = place("upper_arm" + s).translation
        l1, l2 = bones["upper_arm" + s].length, bones["forearm" + s].length
        elbow = two_bone(sh, wrist, l1, l2, (0.5 * sx, 0.3, -1.0))   # elbows down, a little out and back
        place("upper_arm" + s, elbow - sh)
        place("forearm" + s, wrist - tail("upper_arm" + s))
        place("hand" + s, tip - tail("forearm" + s))

    out = {}
    for name, M in pose.items():                   # matrix_basis from pose matrices, parent first
        b = bones[name]
        if b.parent is None:
            out[name] = b.matrix_local.inverted() @ M
        else:
            local_rest = b.parent.matrix_local.inverted() @ b.matrix_local
            out[name] = local_rest.inverted() @ pose[b.parent.name].inverted() @ M
    return out


def seat_designer():
    """Copy DSG_Character into the Studio scene as STU_Designer_* (meshes shared, own armature
    object, so the Designer scene keeps its T-pose) and pose it sitting on STU_Chair_Seat with
    hands on keyboard and mouse. Returns the armature, or None if the Designer scene is missing."""
    src = bpy.data.collections.get("DSG_Character")
    sc = _sc()
    if src is None:
        return None
    for o in [o for o in bpy.data.objects if o.name.startswith(PREFIX + "Designer_")]:
        bpy.data.objects.remove(o, do_unlink=True)
    col = bpy.data.collections.get(PREFIX + "Designer") or bpy.data.collections.new(PREFIX + "Designer")
    if col.name not in sc.collection.children:
        sc.collection.children.link(col)
    arm_src = next(o for o in src.objects if o.type == "ARMATURE")
    copies = {}
    for o in src.objects:
        c = o.copy()
        c.name = PREFIX + ("Designer_Rig" if o is arm_src else "Designer_" + o.name)
        copies[o] = c
        col.objects.link(c)
    for o, c in copies.items():                 # re-parent onto the copies (bone parenting is kept)
        if o.parent in copies:
            c.parent = copies[o.parent]
            c.parent_type, c.parent_bone = o.parent_type, o.parent_bone
            c.matrix_parent_inverse = o.matrix_parent_inverse.copy()   # setting .parent resets it
    arm = copies[arm_src]
    lit = {}                                    # her materials, copied for the studio and lifted a little
    for c in copies.values():
        for slot in getattr(c, "material_slots", []):
            m = slot.material
            if m is None:
                continue
            if m.name not in lit:
                lm = bpy.data.materials.get(PREFIX + "Designer_" + m.name) or m.copy()
                lm.name = PREFIX + "Designer_" + m.name
                b = next((n for n in lm.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
                if b is not None and b.inputs["Alpha"].default_value >= 1.0:
                    b.inputs["Emission Color"].default_value = b.inputs["Base Color"].default_value
                    b.inputs["Emission Strength"].default_value = DESIGNER_GLOW
                lit[m.name] = lm
            slot.link = "OBJECT"                # per object, so the shared mesh keeps its DSG_ material
            slot.material = lit[m.name]

    anchor = bpy.data.objects[PREFIX + "Character_Anchor"].location
    hip_rest = arm_src.data.bones["hips"].head_local
    arm.matrix_world = T(anchor.x, SEAT_HIP_Y, CHAIR_SEAT_Z + THIGH_HALF - SEAT_SINK - hip_rest.z)
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    for name, basis in designer_pose_bases(arm).items():
        arm.pose.bones[name].matrix_basis = basis
    arm.hide_render = True
    try:
        arm.hide_set(True, view_layer=sc.view_layers[0])   # eye-hidden only: still drives the parts
    except RuntimeError:
        pass
    arm["note"] = "seated copy of the Designer (seat_designer); meshes shared with the Designer scene"
    return arm


def show_in_window():
    """Put the Studio scene in the window with Rendered shading (live preview); harmless headless."""
    try:
        win = bpy.context.window or (bpy.context.window_manager.windows[0] if bpy.context.window_manager.windows else None)
        if win is None:
            return
        win.scene = _sc()
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                for sp in area.spaces:
                    if sp.type == "VIEW_3D":
                        sp.shading.type = "RENDERED"
    except Exception as exc:
        print("show_in_window skipped:", exc)


if __name__ == "studio":
    B = build()
    show_in_window()
    obs = [o for o in B.scene.collection.all_objects]
    ph = [m.name for m in bpy.data.materials if m.name.startswith(PREFIX) and m.get("placeholder")]
    print("built", len(obs), "objects;", sum(len(o.data.polygons) for o in obs if o.type == "MESH"), "faces;",
          "placeholders:", ph)
