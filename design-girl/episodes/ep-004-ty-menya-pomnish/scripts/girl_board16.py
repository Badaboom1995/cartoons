"""Shot 16 for anim_girl: she gets up (pushing the chair back and aside), walks to the board, takes the marker from the
tray and draws BOARD_STROKES_16 with the tip on ep4.marker_tip_16(t). Every frame of the shot is an override of the body
tracks: rig world matrix, torso, head, hands, legs (ankle targets, so planted feet stay put) and the chair.
Frames are counted from the shot's first frame (ep4.BOARD_BEATS)."""
import math

import bpy
from mathutils import Matrix, Vector

import ep4

CHAIR_TO = dict(deg=-50.0, roll=0.45, dx=-0.60)   # where her push sends the chair: turn, y and x offsets (world)
CHAIR_BACK = (3, 8, 0.38, 20.0)                        # her push: the chair first rolls straight back this far ...
CHAIR_PUSH = (9, 16)                             # ... then on, back and to the left, until it stops
RISE_FWD = 0.08                                   # she stands up this far in front of where she sat
LEG = 0.552                                       # hip to ankle when she stands (thigh + shin 0.56: knees soft)
STEPS = (4, 5, 5, 5, 5, 4)                        # frames of each step: L, R, L, R, L, then R closes beside L
STEP_LIFT = 0.035
LIFT = 0.015                                      # the tip leaves the board between two lines
DRAW_TORSO = (2.0, 15.0, 0.0)
DRAW_SHARE = 0.3                                  # her head turns this much to the tip, the eyes do the rest
DRAW_POLE = (-1.0, 0.0, -0.3)                     # right elbow out and a little down
AXIS_IN = 0.5                                     # marker axis: half into the board, half along the reach
DOWN_L = (0.30, 0.02, 0.36, 0.31, 0.02, 0.22, 0.3, 0.0, 0.0)   # arm hanging by her side, armature space
TUCK_L = (0.21, -0.05, 0.60, 0.16, -0.11, 0.56, 0.6, 0.0, -0.6)  # hands in front of her tummy while she turns
TUCK_R = (-0.17, -0.07, 0.62, -0.11, -0.13, 0.58, -0.6, 0.0, -0.6)  # the right one closer: the chair rolls past it
TUCK_UNTIL = 26                                                  # frame offset: then the arms swing
TRAY_TIP = (-0.125, -0.377, 0.027)                # marker 1 on the tray: its cap end, board (x, y, off); stage.py
GRAB_OFF = (0.0, 0.05, 0.08)                     # her fist closes this far above and out from it: the mitt stays clear
CLEAR_L = (0.15, -0.22, 0.98, 0.13, -0.35, 0.96, 0.9, 0.3, 0.0)   # hands up off the armrests (anim_girl.CLEAR_L)


def smooth(k):
    k = max(0.0, min(1.0, k))
    return k * k * (3 - 2 * k)


def mix(a, b, k):
    return tuple(x + (y - x) * k for x, y in zip(a, b))


def rz(deg):
    return Matrix.Rotation(math.radians(deg), 3, "Z")


def facing(deg):
    """Her forward (-Y of the rig) in world for a rig yaw."""
    return rz(deg) @ Vector((0.0, -1.0, 0.0))


def mirror(h):
    return (-h[0], h[1], h[2], -h[3], h[4], h[5], -h[6], h[7], h[8])


def swung(h, dy):
    return (h[0], h[1] + dy, h[2], h[3], h[4] + dy * 1.3, h[5], h[6], h[7], h[8])


class Board16:
    def __init__(self, s, ctx, body, A):
        self.s, self.ctx, self.body, self.A = s, ctx, body, A
        self.B = body.bones
        sh = ctx.shot(ep4.BOARD_SHOT)
        self.F, self.last = sh["first_frame"], sh["last_frame"]
        rug = bpy.data.objects.get("STU_Rug")
        if rug:
            pts = [rug.matrix_world @ Vector(c) for c in rug.bound_box]
            self.rug = ([min(p[i] for p in pts) for i in range(3)], [max(p[i] for p in pts) for i in range(3)])
        else:
            self.rug = None
        low = 1e9
        for side in (".L", ".R"):
            ob = bpy.data.objects["STU_Designer_Foot" + side]
            b = self.B[ob.parent_bone]
            M = b.matrix_local @ Matrix.Translation((0, b.length, 0)) @ ob.matrix_parent_inverse @ ob.matrix_basis
            low = min(low, min((M @ v.co).z for v in ob.data.vertices))
        self.ankle_h = self.B["foot.L"].head_local.z - low          # sole to ankle
        self.hip = {s_: self.B["thigh" + s_].head_local.copy() for s_ in (".L", ".R")}
        self.grip = Vector(ep4.BOARD_MARKER_GRIP["tip"])
        self.n_out = rz(ep4.BOARD_YAW_DEG) @ Vector((0.0, -1.0, 0.0))
        self.board_x = rz(ep4.BOARD_YAW_DEG) @ Vector((1.0, 0.0, 0.0))
        self.yaw_board = ep4.BOARD_YAW_DEG + 180.0
        anchor = bpy.data.objects["STU_Claude_Dock_Anchor"].matrix_world.translation
        self.clawd = anchor + Vector((0, 0, 0.08))

    # ------------------------------------------------------------ helpers
    def floor(self, x, y):
        if self.rug and self.rug[0][0] <= x <= self.rug[1][0] and self.rug[0][1] <= y <= self.rug[1][1]:
            return self.rug[1][2]
        return 0.0

    def ankle(self, xy):
        return Vector((xy[0], xy[1], self.floor(xy[0], xy[1]) + self.ankle_h + 0.001))

    def footprint(self, pos, yaw, side):
        off = rz(yaw) @ Vector((self.hip[side].x, 0.0, 0.0))
        return self.ankle(pos + off.to_2d()), yaw

    def world(self, xy, hz, yaw):
        return Matrix.Translation((xy[0], xy[1], hz - self.hip[".L"].z)) @ Matrix.Rotation(math.radians(yaw), 4, "Z")

    def hips_cap(self, xy, yaw, feet):
        """Highest hip height from which both legs still reach their ankles."""
        cap = 1e9
        for side, (a, _) in feet.items():
            h = Vector(xy) + (rz(yaw) @ Vector((self.hip[side].x, 0.0, 0.0))).to_2d()
            d = (a.to_2d() - h).length
            cap = min(cap, a.z + math.sqrt(max(0.0, LEG * LEG - d * d)))
        return cap

    def legs(self, W, yaw, feet):
        Winv = W.inverted()
        out = {}
        for side, (a, fyaw) in feet.items():
            out[side] = {"ankle": Winv @ a, "pole": Vector((0.0, -1.0, 0.2)),
                         "rot": Matrix.Rotation(math.radians(fyaw - yaw), 3, "Z")}
        return out

    def shoulder(self, W, torso, head):
        pose, _ = self.A.solve(self.B, torso, head, {".L": DOWN_L, ".R": mirror(DOWN_L)},
                               {".L": (0.0, 0.0), ".R": (0.0, 0.0)})
        return W @ pose["upper_arm.R"].translation

    def hand_to(self, W, torso, head, other, tip, axis, pole=DRAW_POLE):
        """Right hand (armature tuple) that puts the grip tip on a world point with the marker along axis."""
        Winv = W.inverted()
        t, a = Winv @ tip, (Winv.to_3x3() @ axis).normalized()
        wrist = t - a * self.grip.y
        legs = {".L": (0.0, 0.0), ".R": (0.0, 0.0)}
        for _ in range(5):
            h = (*wrist, *(wrist + a * 0.14), *pole)
            pose, _ = self.A.solve(self.B, torso, head, {".L": other, ".R": h}, legs)
            wrist = wrist + (t - pose["hand.R"] @ self.grip)
        return (*wrist, *(wrist + a * 0.14), *pole)

    def draw_axis(self, W, torso, head, tip):
        sh = self.shoulder(W, torso, head)
        return ((-self.n_out) * AXIS_IN + (tip - sh).normalized() * (1 - AXIS_IN)).normalized()

    def tip_at(self, t):
        """World tip point while drawing, with the lift between lines as a smooth arc out of the board."""
        x, y, touching = ep4.marker_tip_16(t)
        off = 0.0
        if not touching and t < ep4.BOARD_BEATS["draw"][1]:
            a = t
            while a > t - ep4.BOARD_LIFT_FRAMES - 1 and not ep4.marker_tip_16(a - 0.05)[2]:
                a -= 0.05
            k = (t - a) / ep4.BOARD_LIFT_FRAMES
            off = LIFT * math.sin(math.pi * max(0.0, min(1.0, k)))
        return ep4.board_point(x, y, off), touching

    # ------------------------------------------------------------ the plan
    def build(self):
        s, F, A, body = self.s, self.F, self.A, self.body
        tr = s.t
        bt = ep4.BOARD_BEATS
        # seated, as the tracks leave her on the first frame of the shot
        loc0, chair0, yaw0, roll0 = tr["loc"].at(F), tr["chair"].at(F)[0], tr["yaw"].at(F)[0], tr["roll"].at(F)[0]
        W0 = body.world(loc0, chair0, yaw0, roll0)
        torso0, head0, L0, R0 = tr["torso"].at(F), tr["head"].at(F), tr["L"].at(F), tr["R"].at(F)
        pose0, _ = A.solve(self.B, torso0, head0, {".L": L0, ".R": R0}, {".L": A.SEATED, ".R": A.SEATED})
        psi0 = chair0 + yaw0
        p0 = W0.translation.to_2d()
        hz0 = (W0 @ self.hip[".L"]).z
        seat_feet = {sd: (W0 @ pose0["foot" + sd].translation, psi0) for sd in (".L", ".R")}

        P1 = p0 + facing(psi0).to_2d() * RISE_FWD
        P2 = Vector(ep4.BOARD_STAND_SPOT)
        d = P2 - P1
        hd = math.degrees(math.atan2(d.x, -d.y))
        turn = (hd - psi0) % 360.0                       # she turns to her left, her face to the room
        hd = psi0 + turn
        yb = self.yaw_board
        while yb - hd > 180:
            yb -= 360
        while yb - hd < -180:
            yb += 360
        S1 = P1 - facing(psi0).to_2d() * 0.09          # the first step goes back, away from the desk edge
        stations = [(P1, psi0), (S1, psi0 + 0.3 * turn)]
        d = P2 - S1
        hd = psi0 + (math.degrees(math.atan2(d.x, -d.y)) - psi0) % 360.0
        for k in range(1, 5):
            yaw = (psi0 + 0.75 * turn, psi0 + 0.95 * turn, hd, yb)[k - 1]
            stations.append((S1 + (P2 - S1) * (k / 4), yaw))
        hz_stand = self.ankle(P1).z + LEG

        # walk schedule: (side, from station, to station, first frame, last frame)
        sides, targets = [".L", ".R", ".L", ".R", ".L", ".R"], [1, 2, 3, 4, 5, 5]
        sched, f = [], bt["walk"][0]
        at = {".L": 0, ".R": 0}
        sig_keys = [(f, 0.0)]
        for side, to_k, n in zip(sides, targets, STEPS):
            sched.append((side, at[side], to_k, f, f + n))
            at[side] = to_k
            f += n
            sig_keys.append((f, min(at.values()) + (0.5 if at[".L"] != at[".R"] else 0.0)))
        sig_keys[-1] = (sig_keys[-1][0], 5.0)

        def sigma(t):
            for (a, va), (b, vb) in zip(sig_keys, sig_keys[1:]):
                if t <= b:
                    return va + (vb - va) * (t - a) / (b - a)
            return sig_keys[-1][1]

        def station(sg):
            i = min(int(sg), len(stations) - 2)
            k = sg - i
            (pa, ya), (pb, yb_) = stations[i], stations[i + 1]
            return pa + (pb - pa) * k, ya + (yb_ - ya) * k

        def feet_walk(t):
            out = {}
            for side in (".L", ".R"):
                k_at = 0
                swing = None
                for sd, ka, kb, a, b in sched:
                    if sd != side:
                        continue
                    if t >= b:
                        k_at = kb
                    elif a <= t < b:
                        swing = (ka, kb, (t - a) / (b - a))
                if swing:
                    ka, kb, k = swing
                    (aa, ya), (ab, yb_) = self.footprint(*stations[ka], side), self.footprint(*stations[kb], side)
                    e = smooth(k)
                    p = aa + (ab - aa) * e
                    p.z += STEP_LIFT * math.sin(math.pi * k)
                    out[side] = (p, ya + (yb_ - ya) * e)
                else:
                    out[side] = self.footprint(*stations[k_at], side)
            return out

        # the marker on the tray and the first point of the drawing
        mk = bpy.data.objects.get("%sBoard_Marker_%d" % (ep4.PREFIX, ep4.BOARD_MARKER))
        tray_tip = ep4.board_point(TRAY_TIP[0] + GRAB_OFF[0], TRAY_TIP[1] + GRAB_OFF[1], TRAY_TIP[2] + GRAB_OFF[2])
        tray_axis = (self.board_x + Vector((0.0, 0.0, -0.8))).normalized()
        first = ep4.BOARD_STROKES_16[0][0]
        start_tip = ep4.board_point(first[0], first[1], LIFT)

        v11 = next((l for l in self.ctx.shot(ep4.BOARD_SHOT)["lines"]), None)
        glance = None
        if v11:
            g0 = v11["first_frame"] - F + 3
            glance = (g0, g0 + 5, g0 + 13, g0 + 19)

        s.override = getattr(s, "override", {})
        gaze_keys = []
        for t in range(0, self.last - F + 1):
            f = F + t
            back = facing(chair0) * -CHAIR_BACK[2]
            mid = (chair0 + CHAIR_BACK[3], roll0 + back.y, back.x)
            if t < CHAIR_PUSH[0]:
                k = smooth((t - CHAIR_BACK[0]) / (CHAIR_BACK[1] - CHAIR_BACK[0]))
                chair = mix((chair0, roll0, 0.0), mid, k)
            else:
                k = min(1.0, (t - CHAIR_PUSH[0]) / (CHAIR_PUSH[1] - CHAIR_PUSH[0]))
                k = 1 - (1 - k) ** 2
                chair = mix(mid, (CHAIR_TO["deg"], CHAIR_TO["roll"], CHAIR_TO["dx"]), k)
            gaze = (0.0, 0.0)
            if t < bt["stand"][1]:
                k = smooth((t - 3) / 9.0)
                xy = p0 + (P1 - p0) * k
                yaw = psi0
                hz = hz0 + (hz_stand - hz0) * k
                kf = smooth((t - 6) / 5.0)
                feet = {}
                for sd in (".L", ".R"):
                    a0 = seat_feet[sd][0]
                    a1 = self.footprint(P1, psi0, sd)[0]
                    feet[sd] = (a0 + (a1 - a0) * kf, psi0)
                if t < 4:
                    torso = mix(torso0, (18.0, 0.0, 0.0), smooth(t / 4.0))
                else:
                    torso = mix((18.0, 0.0, 0.0), (2.0, 0.0, 0.0), smooth((t - 4) / 8.0))
                up = lambda h: (h[0], h[1], h[2] + 0.07, h[3], h[4], h[5] + 0.07, *h[6:])
                if t < 4:                                # a push on the armrests, and the hands come up off them
                    kh = smooth((t - 1) / 3.0)
                    L, R = mix(L0, up(L0), kh), mix(R0, up(R0), kh)
                else:
                    kh = smooth((t - 4) / 6.0)
                    L, R = mix(up(L0), TUCK_L, kh), mix(up(R0), TUCK_R, kh)
                head = mix(head0, (0.0, 0.0, 0.0), smooth(t / 12.0))
                gaze = mix(tr["gaze"].at(F), (0.0, 0.0), smooth(t / 8.0))
            elif t <= bt["walk"][1]:
                sg = sigma(t)
                xy, yaw = station(sg)
                feet = feet_walk(t)
                hz = hz_stand
                torso = (4.0, 0.0, 0.0)
                ph = math.sin(math.pi * sg * 2) * smooth((t - bt["walk"][0] - 6) / 4.0) * smooth((bt["walk"][1] - t) / 3.0)
                L, R = swung(DOWN_L, 0.06 * ph), swung(mirror(DOWN_L), -0.06 * ph)
                kt = smooth((t - TUCK_UNTIL) / 6.0)
                L, R = mix(TUCK_L, L, kt), mix(TUCK_R, R, kt)
                aimh, gaze = body.aim(ep4.board_point(-0.2, 0.0, 0.0), Vector((xy.x, xy.y, hz - 0.64)), 0.0, yaw,
                                      torso, share=0.6)
                head = (max(-10.0, min(15.0, aimh[0])), max(-55.0, min(55.0, aimh[1])), 0.0)
                gaze = (0.0, 0.0) if abs(aimh[1]) > 55 else gaze
            else:
                xy, yaw = station(5.0)
                feet = feet_walk(t)
                hz = hz_stand
                torso = mix((4.0, 0.0, 0.0), DRAW_TORSO, smooth((t - bt["walk"][1]) / 6.0))
                L = DOWN_L
            hz = min(hz, self.hips_cap(xy, yaw, feet))
            W = self.world(xy, hz, yaw)
            rig_loc = W.translation

            if t > bt["walk"][1] - 12:
                # the right hand: reach for the tray, take the marker, bring it up, draw
                blend = None
                if t <= bt["pick"][0]:
                    tip, axis = tray_tip, tray_axis
                    look = tray_tip
                elif t < bt["draw"][0]:
                    k = smooth((t - bt["pick"][0] - 2) / (bt["draw"][0] - 1 - bt["pick"][0] - 2))
                    tip = tray_tip + (start_tip - tray_tip) * k
                    tip = tip + (-self.n_out) * -0.05 * math.sin(math.pi * k)
                    ax1 = self.draw_axis(W, torso, (0.0, 0.0, 0.0), start_tip)
                    axis = (tray_axis + (ax1 - tray_axis) * k).normalized()
                    look = tip if k > 0.3 else tray_tip
                    blend = k                            # the arm moves between the two hand poses, not the tip
                else:
                    tip, _ = self.tip_at(t)
                    axis = self.draw_axis(W, torso, (0.0, 0.0, 0.0), tip)
                    look = tip
                head, gaze = body.aim(look, rig_loc, 0.0, yaw, torso, share=DRAW_SHARE if t >= bt["walk"][1] - 4 else 0.6)
                if glance and glance[0] <= t <= glance[3]:
                    w = smooth((t - glance[0]) / (glance[1] - glance[0])) if t < glance[1] else \
                        (1.0 if t <= glance[2] else 1 - smooth((t - glance[2]) / (glance[3] - glance[2])))
                    hg, gg = body.aim(self.clawd, rig_loc, 0.0, yaw, torso, share=1.0)
                    hg = (max(-10.0, min(10.0, hg[0])), max(-75.0, min(75.0, hg[1])), 0.0)
                    gg = (-ep4_lookx(A) if hg[1] < 0 else ep4_lookx(A), 0.0)
                    head = mix(head, hg, w * 0.8)
                    gaze = mix(gaze, gg, w)
                if blend is None:
                    Rh = self.hand_to(W, torso, head, L, tip, axis)
                else:
                    ax1 = self.draw_axis(W, torso, (0.0, 0.0, 0.0), start_tip)
                    Ra = self.hand_to(W, torso, head, L, tray_tip, tray_axis)
                    Rb = self.hand_to(W, torso, head, L, start_tip, ax1)
                    Rh = mix(Ra, Rb, blend)
                    out = Winv3 = W.inverted().to_3x3() @ ((self.board_x * 0.08 + Vector((0.0, 0.0, -0.05))) * math.sin(math.pi * blend))
                    Rh = (Rh[0] + out.x, Rh[1] + out.y, Rh[2] + out.z, Rh[3] + out.x, Rh[4] + out.y, Rh[5] + out.z, *Rh[6:])
                if t > bt["walk"][1] - 12 and t <= bt["walk"][1]:
                    Rw = swung(mirror(DOWN_L), 0.0)
                    R = mix(Rw, Rh, smooth((t - (bt["walk"][1] - 12)) / 12.0))
                else:
                    R = Rh
            gaze_keys.append((f, tuple(gaze)))
            s.override[f] = dict(W=W, chair=chair, torso=tuple(torso), head=tuple(head), hands={".L": L, ".R": R},
                                 legs=self.legs(W, yaw, feet))
        g = s.t["gaze"]
        g.keys = sorted([k for k in g.keys if not F <= k[0] <= self.last] + gaze_keys)
        s.board16 = dict(P1=P1, P2=P2, stations=stations, hz=hz_stand)


def ep4_lookx(A):
    return A.LOOK_X
