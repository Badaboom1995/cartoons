"""Builds ep-003.blend from a fresh studio.blend.

Blender -b --factory-startup CHARACTER/scene/locations/studio/studio.blend --python EP/scripts/build_blend.py

Parts run in order. A part whose file does not exist yet is skipped. A part that fails stops the build before anything
is saved, so a good ep-003.blend is never replaced by a broken one. EP3_OUTPUT overrides the output path for test builds.
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

import ep3  # noqa: E402

PARTS = ("stage", "anim_clawd", "anim_girl", "steam_part", "screens")


def output_path():
    return Path(os.environ.get("EP3_OUTPUT", ep3.OUTPUT_BLEND)).resolve()


def run_parts(ctx):
    for name in PARTS:
        if not (SCRIPTS / (name + ".py")).exists():
            print("build_blend: %s.py is not there yet, skipped" % name)
            continue
        print("build_blend: running", name)
        importlib.import_module(name).build(ctx)


def save(ctx, path):
    if path == ep3.STUDIO_BLEND.resolve():
        raise RuntimeError("refusing to save over studio.blend")
    path.parent.mkdir(parents=True, exist_ok=True)
    ctx.scene.frame_set(ctx.frame_start)
    bpy.ops.wm.save_as_mainfile(filepath=str(path), relative_remap=True)
    bpy.ops.file.make_paths_relative()                      # the voice files were added with absolute paths
    bpy.ops.wm.save_mainfile()
    print("build_blend: saved", path)


def main():
    ctx = ep3.Ctx()
    try:
        run_parts(ctx)
        save(ctx, output_path())
    except Exception:
        traceback.print_exc()
        print("build_blend: FAILED, nothing saved")
        sys.exit(1)


main()
