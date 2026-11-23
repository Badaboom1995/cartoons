# Episode 2: "Surprise Me"

Vertical 9:16, 24 fps, about 85–90 s (fit it to the voice lengths). Same studio, girl and Clawd (Claude on the desk).
Voices: Girl is Gemini TTS "Leda". Claude is Gemini TTS "Puck". Files are in `audio/voice/` and named in line order.

## Dialogue

| # | File | Length | Who | Line |
|---|---|---|---|---|
| 1 | v01_girl_hey_claude.wav | 1.68 s | Girl | "Hey, Claude…" |
| 2 | v02_claude_im_here.wav | 1.44 s | Claude | "Yep, I'm here!" |
| 3 | v03_girl_deadline.wav | 5.60 s | Girl | "The deadline is so close… and I still have zero ideas." |
| 4 | v04_girl_surprise_me.wav | 3.88 s | Girl | "I need some inspiration… surprise me." |
| 5 | v05_claude_cooking.wav | 2.00 s | Claude | "Say less. Cooking!" |
| 5b | v05b_girl_nap.wav | 3.96 s | Girl | "Okay… I'm gonna nap a little." (sleepy, content) |
| 6 | v06_girl_party.wav | 5.64 s | Girl | "Huh?! … Claude… was there a party just now?" (groggy, confused, then suspicious) |
| 7 | v07_claude_no_party.wav | 4.72 s | Claude | "A party? … Nooo. No party. … Definitely… no party." (too fast, too innocent) |
| 8 | v08_girl_moodboard.wav | 4.92 s | Girl | "My moodboard… my deadline… Claude!" |
| 9 | v09_claude_relax.wav | 2.48 s | Claude | "Hey, relax. Look." |
| 10 | v10_girl_beautiful.wav | 5.20 s | Girl | "…Oh. That's… actually beautiful." |
| 11 | v11_girl_walk.wav | 4.32 s | Girl | "Thank you, Claude. Now I can finally go for a walk." |
| 12 | v12_claude_go.wav | 2.80 s | Claude | "Go! Enjoy it. I've got this." |
| 13 | v13_claude_oh_no.wav | 1.20 s | Claude | "…oh no." (whisper) |

## Shot list (times are approximate: re-time to the audio)

### Scene 1: Stuck
1. **Wide**, slow push-in. Late afternoon. She's slumped, chin in hand, sleepy face. The laptop shows an empty grey moodboard. Room tone, clock tick.
2. **Keys close-up**, static. Her finger presses the mic key. A mic icon and a moving sound wave pop up on the laptop. Key click and chime. **Line 1.**
3. **Clawd close-up**, low angle, small push-in. Clawd hops, turns to her, and the listening rings pulse. **Line 2.**
4. **Face close-up**, very slow push-in. Sleepy, then hmm, with a sigh. **Line 3.**
5. **Over Clawd's shoulder** (her face in the background), static. She looks at Clawd with a small, trusting smile. **Line 4.**
6. **Clawd close-up**, quick push-in. Clawd leans in with a mischievous glint. **Line 5.**

### Scene 2: She dozes off
7. **Front medium**, slow pull-out (longer shot, about 6.5 s). She smiles (^_^) on "Okay…", leans back, and her eyes get heavy (lids half down) on "I'm gonna nap a little"; they close (gentle ∪ arcs) as she finishes the line. **Line 5b.** Daylight fades to dusk. Clawd watches her for a beat, then slowly turns to the laptop, and its eyes glint. Big soft "Z z Z" letters rise from just above her head and fade, in a loop, while she sleeps (also in the party shots 9–12, bigger in the far fisheye wide). They vanish on the wake cut.

### Scene 3: Claude goes mad (about 10–13 s)
8. **Screen close-up**, fast push-in. The moodboard tiles flicker, shuffle and burst into neon shapes and confetti. Synth-disco music drops.
9. **Wide fisheye**, slow roll of about 10° and a bob on the beat. The walls, posters and shelf glow neon pink, cyan and purple. A **disco ball comes down from the ceiling** and spins, with light spots sweeping the room. She keeps sleeping in the middle. Clawd dances on the desk.
10. **Disco ball close-up**, low angle, orbiting. The ball spins and throws sparkles at the lens.
11. **Clawd close-up**, handheld shake and a whip pan in. Clawd spins and hops.
12. **Top-down fisheye**, slow spin. Confetti rains on the desk, the keyboard and her.

### Scene 4: Wake up
13. **Face close-up**, crash zoom. She jolts awake: on this cut the party is simply gone, like a dream (record scratch; music, neon, disco ball, party lights and confetti all vanish on the same frame, the room is plain dusk again). Confused, then suspicious "hmm". **Line 6.**
14. **Clawd close-up**, static. Clawd stands there perfectly normal and looks caught: a quick innocent "no, no" head wobble while he denies it, a shifty glance away on "Definitely…", back to her for "no party". **Line 7.**
15. **Face close-up**, slight handheld shake. Panic face (flat mouths). The room is normal dusk. **Line 8.**

### Scene 5: The moodboard
16. **Over Clawd's shoulder**, slow push. Clawd turns to the laptop. **Line 9.**
17. **Screen close-up**, slow push-in. The swatches pop in one by one, then a finished moodboard in neon-pastel colors taken from the party. The room is already normal (the party was "a dream").
18. **Face close-up**, slow push-in. Panic, then hmm, then calm and delighted. **Line 10.**

### Scene 6: Going for a walk
19. **Front medium**, static. Big relieved smile. **Line 11.**
20. **Clawd close-up**. A proud hop. **Line 12.**
21. **Wide** (normal lens), static. She stands up, puts her headphones around her neck and walks out of the frame. The room is warm and quiet again. Footsteps.

### Scene 7: Cleanup tag
22. **Clawd close-up**, very slow push-in. Clawd looks left, then right. Silence, clock tick.
23. **Desk insert, top-down**. Confetti all over the desk. One last piece floats down.
24. **Clawd close-up**, snap zoom. Eyes go wide. **Line 13.**
25. **Top-down, fast-motion**. Clawd zips around the desk, sweeping the confetti into a pile and hiding it behind the laptop. Fast, squeaky music.
26. **Clawd close-up**, static. An innocent pose. It blinks at the camera, then sneezes out one piece of confetti.
27. ~~**End card**: "Surprise me. 🪩" with a chime.~~ Removed: the episode ends on shot 26 (Clawd's confetti sneeze). Set `END_CARD = True` in `episode2.py` to bring it back.

## Notes
- Her eyes have two looks only: white with a black pupil (open; tired and suspicious add a skin-coloured lid over the top, suspicious glances towards Clawd; shocked and panic shrink the pupil) and closed arcs (^_^ for smile and delighted, a gentle ∪ while asleep). The blue-iris Studio eye sets are not used in EP2.
- Voice input: she presses the mic key once at the start. After that the mic icon stays on, and the sound wave moves whenever she talks.
- Fisheye in EEVEE: a very wide lens (about 12 mm) plus barrel distortion in the compositor (Lens Distortion node), turned on only for the fisheye shots.
- Cameras now move: push-ins, pull-outs, rolls, shakes, crash zooms, orbits. They are no longer static cuts.
