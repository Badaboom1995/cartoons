"""Shared contract of the EP3 Blender build. Every part is a module with build(ctx).

Build order (build_blend.py): stage -> anim_clawd -> anim_girl -> screens. The build always starts from a fresh
studio.blend, so a part does not need to clean up after itself. Everything a part adds is named EP3_*.
"""
import json
from pathlib import Path

import bpy

EP = Path(__file__).resolve().parents[1]
CHARACTER = EP.parents[1]
STUDIO_BLEND = CHARACTER / "scene" / "locations" / "studio" / "studio.blend"
CLAWD_BLEND = CHARACTER / "scene" / "characters" / "clawd" / "clawd.blend"
OUTPUT_BLEND = EP / "ep-003.blend"
OVERLAYS = EP / "overlays"

PREFIX = "EP3_"
SCENE = "EP3_Posidi"
ROOT_COLLECTION = "EP3_Episode"
GIRL_RIG = "STU_Designer_Rig"     # already in studio.blend
CLAWD_RIG = "EP3_Clawd_Rig"       # created by anim_clawd on STU_Claude_Dock_Anchor
SCREEN = "STU_Screen_Laptop"
CUP = "STU_Tea_Cup"


def camera_name(shot_id):
    return f"EP3_Cam_{shot_id:02d}"


class Ctx:
    def __init__(self, scene=None):
        self.scene = scene or bpy.context.scene
        self.timeline = json.loads((EP / "timeline.json").read_text(encoding="utf-8"))
        self.fps = self.timeline["fps"]
        self.frame_start = self.timeline["frame_start"]
        self.frame_end = self.timeline["frame_end"]
        self.shots = self.timeline["shots"]

    def shot(self, shot_id):
        return next(s for s in self.shots if s["id"] == shot_id)

    def line(self, line_id):
        return next(l for s in self.shots for l in s["lines"] if l["id"] == line_id)

    def lines(self, who=None):
        return [l for s in self.shots for l in s["lines"] if who is None or l["who"] == who]

    def sfx(self, sfx_id):
        """A sound effect of the timeline: {"id", "file", "gain", "first_frame"}."""
        return next(f for s in self.shots for f in s.get("sfx", []) if f["id"] == sfx_id)

    def all_sfx(self):
        return [f for s in self.shots for f in s.get("sfx", [])]

    def audio_path(self, line):
        return EP / line["file"]

    def collection(self, name):
        """EP3_<name> under the episode's root collection, created on first use."""
        root = bpy.data.collections.get(ROOT_COLLECTION)
        if root is None:
            root = bpy.data.collections.new(ROOT_COLLECTION)
            self.scene.collection.children.link(root)
        full = PREFIX + name
        col = bpy.data.collections.get(full)
        if col is None:
            col = bpy.data.collections.new(full)
            root.children.link(col)
        return col
