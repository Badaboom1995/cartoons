"""Renders the picture of ep-004.blend to one temporary video (no sound, no card), for finish.py.

    Blender -b ep-004.blend --python scripts/render.py -- <out.mp4>

Straight to video, no frame folder in the project. The scene's own render settings (engine, samples, 1080x1920, 24 fps).
"""
import sys

import bpy

out = sys.argv[sys.argv.index("--") + 1]
sc = bpy.context.scene
r = sc.render
r.filepath = out
r.use_file_extension = False
r.image_settings.media_type = "VIDEO" if hasattr(r.image_settings, "media_type") else r.image_settings.file_format
r.image_settings.file_format = "FFMPEG"
r.ffmpeg.format = "MPEG4"
r.ffmpeg.codec = "H264"
r.ffmpeg.constant_rate_factor = "LOSSLESS"
r.ffmpeg.ffmpeg_preset = "GOOD"
r.ffmpeg.audio_codec = "NONE"
print("render: %s, frames %d-%d, %dx%d" % (out, sc.frame_start, sc.frame_end, r.resolution_x, r.resolution_y))
bpy.ops.render.render(animation=True)
print("render: done", out)
