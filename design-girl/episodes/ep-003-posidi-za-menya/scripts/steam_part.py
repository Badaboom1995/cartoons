"""EP3 steam: the reusable cup steam on her tea, replacing the studio's static wisp for the whole episode."""
import sys

import bpy

import ep3
import stage

sys.path.insert(0, str(ep3.CHARACTER / "scene" / "props" / "cup" / "scripts"))
import steam  # noqa: E402

OLD_STEAM = "STU_Tea_Steam"
FACE_TARGET = ep3.PREFIX + "Face_Target"      # made by stage: the point between her eyes
FACE_CLEARANCE = 0.15                         # the wisps are gone before their column gets this close to her face
DAY_STRENGTH = 1.0
EVENING_STRENGTH = 0.72                       # a pale wisp would glow in the darker room


def build(ctx):
    old = bpy.data.objects[OLD_STEAM]
    old.animation_data_clear()
    old.hide_render = old.hide_viewport = True
    first, last = stage.timelapse_frames(ctx)
    steam.add_steam(
        ctx.scene, bpy.data.objects[ep3.CUP], ctx.frame_start, ctx.frame_end,
        name=ep3.PREFIX + "Steam", collection=ctx.collection("Steam"),
        fade_near=(bpy.data.objects[FACE_TARGET], FACE_CLEARANCE),
        hidden_spans=[(ctx.shot(11)["first_frame"], ctx.shot(12)["last_frame"])],     # the cup at her mouth, in the fisheye
        strength_keys=[(ctx.frame_start, DAY_STRENGTH), (first, DAY_STRENGTH), (last, EVENING_STRENGTH)],
    )
