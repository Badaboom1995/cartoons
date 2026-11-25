"""Builds ep-004.blend from a fresh studio.blend.

/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
    CHARACTER/scene/locations/studio/studio.blend --python EP/scripts/build_blend.py

Parts run in order. A part whose file does not exist yet is skipped. A part that fails stops the build before anything
is saved, so a good ep-004.blend is never replaced by a broken one.
EP4_OUTPUT overrides the output path for test builds; EP4_PARTS (comma-separated) runs only the parts named.
"""
import importlib
import os
import sys
import traceback
from pathlib import Path

import bpy

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import ep4  # noqa: E402

PARTS = ("stage", "anim_clawd", "anim_girl", "cameras")


def output_path():
    return Path(os.environ.get("EP4_OUTPUT", ep4.OUTPUT_BLEND)).resolve()


def parts():
    only = os.environ.get("EP4_PARTS")
    return [p for p in PARTS if not only or p in only.split(",")]


def run_parts(ctx):
    for name in parts():
        if not (SCRIPTS / (name + ".py")).exists():
            print("build_blend: %s.py is not there yet, skipped" % name)
            continue
        print("build_blend: running", name)
        importlib.import_module(name).build(ctx)


def viewports_for_review():
    """The file opens the way it is reviewed: textures, the scene's own lights and world, through the shot camera.
    Material Preview with scene lights, because Blender drops a saved Rendered mode when it opens a file."""
    for screen in bpy.data.screens:
        for area in screen.areas:
            for space in area.spaces:
                if space.type == "VIEW_3D":
                    space.shading.type = "MATERIAL"
                    space.shading.use_scene_lights = True
                    space.shading.use_scene_world = True
                    space.region_3d.view_perspective = "CAMERA"


def save(ctx, path):
    if path == ep4.STUDIO_BLEND.resolve():
        raise RuntimeError("refusing to save over studio.blend")
    path.parent.mkdir(parents=True, exist_ok=True)
    viewports_for_review()
    ctx.scene.frame_set(ctx.frame_start)
    bpy.ops.wm.save_as_mainfile(filepath=str(path), relative_remap=True)
    bpy.ops.file.make_paths_relative()                      # the sound files were added with absolute paths
    bpy.ops.wm.save_mainfile()
    print("build_blend: saved", path)


def main():
    ctx = ep4.Ctx()
    try:
        run_parts(ctx)
        save(ctx, output_path())
    except Exception:
        traceback.print_exc()
        print("build_blend: FAILED, nothing saved")
        sys.exit(1)


main()
