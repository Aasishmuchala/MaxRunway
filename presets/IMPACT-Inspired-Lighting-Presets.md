# IMPACT-inspired lighting preset library

14 September 2026 · 3ds Max 2026 / V-Ray 7.2 planning handoff

## What this pack provides

**Eight architectural lighting recipes, one specialty studio recipe, and an Original Scene reset specification.** These cover the major lighting families visible in the agreed latest five IMPACT 3D films. They are our authored recreations, not the studio's extracted settings or proprietary preset files. A finished, graded image does not uniquely reveal its lights, intensities, environment or exposure.

The companion `IMPACT-Inspired-Lighting-Presets.json` records the recipes and safety rules for future plugin integration. **It is not an executable MaxScript, V-Ray preset or one-click importer.** No loader was implemented in this planning update. Nothing has been installed, applied to the huge scene or test-rendered on the other PC.

Relighting is optional: the original scene remains the baseline. Materials, textures, geometry and saved camera motion stay unchanged. New lighting will necessarily change illumination and reflections; it cannot simultaneously preserve the original rendered pixels. Approve the lighting variant before full-sequence rendering.

## Reference review and limits

The channel's Videos tab was checked on 14 September 2026; Shorts and Live were excluded. The expanded lighting review inspected 335 timestamped midpoint samples from automatically detected intervals, supplementing the earlier 120 uniformly spaced samples. Interval detection can split transitions or miss changes; these counts are not verified editorial shot counts.

| Film | Upload date | Expanded samples | Useful lighting evidence |
| --- | --- | ---: | --- |
| [Century Mirai](https://www.youtube.com/watch?v=tO-Vl1hLa6U) | 25 June 2026 | 100 | 00:14 raking window light; 00:29 soft bedroom; 01:34 daylight pool; 02:07 evening pool; 02:29 warm workplace fixtures. |
| [Riviera Crown](https://www.youtube.com/watch?v=dKymE__UK68) | 30 April 2026 | 49 | 00:16 theatrical chess insert; 01:05 layered warm lobby; 01:30 direct floor patch; 01:55 warm landscape fixtures against dusk. |
| [Encanto Lansum & MK](https://www.youtube.com/watch?v=1KFbhDrLn-0) | 24 April 2026 | 81 | 00:13 low warm sun; 00:46 sunlit reception; 01:31 soft bedroom; 02:00 dappled garden; 02:47 dusk skyline. |
| [Discover the Sixth Element Pavani Mirai](https://www.youtube.com/watch?v=LZfvC9NAMjA) | 4 February 2026 | 83 | 00:36 bright neutral facade; 00:51 canopy shade; 01:18 pale lobby; 02:38 warm spa; 03:02 dusk tower. |
| [Redefining Architecture... Presidential Towers](https://www.youtube.com/watch?v=Q3zCo73GNu0) | 24 December 2025 | 22 | 00:02 grazing water detail; 00:17 low warm sun; 00:31 backlit pool terrace; 00:44 directional garden wall light. |

The automated video-question/indexing route failed. Readable cached review videos were used for direct visual inspection instead. This is a dense sampled visual review, **not continuous playback or audio audition**. Review copies were 1280 pixels wide; inspected samples were 480 pixels wide. Neither proves the references' original mastering resolution or their fine 4K detail. The library does not claim to enumerate every undisclosed setting, every frame or the entire channel.

## Preset selector

All numbers below are **our starting suggestions for calibration**, not measurements recovered from the films. Parentheses give an exploration range. Do not apply them blindly to the production scene.

| ID / recipe | Proposed starting lighting controls | Pair with |
| --- | --- | --- |
| P00 · Original Scene | No authored changes; restore the exact captured baseline | Original approved display/grade |
| P01 · Clear Neutral Daylight | Sun elevation 45° (35–55°); Sun size multiplier 1.5 (1–2) | Neutral daylight grade |
| P02 · Dappled Garden Backlight | Sun elevation 25° (15–35°); size 2 (1–3); existing canopy | Natural greens, restrained warm edges |
| P03 · Golden Low Sun | Sun elevation 7° (4–12°); size 2 (1.5–3) | Warm highlights, readable cooler shade |
| P04 · Soft Window Interior | Existing broad window/sky light; selected practicals 3200 K (3000–3500 K) | Clean cream/white balance |
| P05 · Warm Raking Interior | Sun elevation 12° (8–20°); size 1.5 (1–2); selected practicals 2900 K (2700–3000 K) | Local warmth, protected stone/fabric |
| P06 · Warm Practical Luxury | Existing cove, accent and decorative fixtures; 3000 K (2700–3200 K) | Cream/gold/wood separation |
| P07 · Blue Hour + Warm Practicals | Twilight elevation −4° (−6 to −2°), only with a compatible sky; existing practicals 3000 K (2700–3200 K) | Cool ambient / warm occupied spaces |
| P08 · Low-Key Material Detail | Existing grazing window/fixture; retain its colour and source shape | Deep but readable material contrast |
| P09 · Theatrical Studio Specialty | Existing studio key/rim lights; 5000 K (4500–5500 K) | Controlled dark surround and edge highlights |

Sun elevation is measured above the horizon, not a guessed clock time. World azimuth, site north, geographic time/date and HDRI orientation remain unset until the actual scene is audited. V-Ray Sun uses its supported sky/colour controls, **not a Kelvin temperature input**. Fixture Kelvin suggestions apply only to supported temperature-mode lights; they are not camera white balance or a command to retint an HDRI. Sun size is a softness control, not a light-intensity ratio. Verify controls against the target build. [Chaos Sun parameter reference](https://docs.chaos.com/pages/viewpage.action?pageId=64598504), [Chaos VRayLight](https://docs-chaos.atlassian.net/wiki/spaces/VMAX/pages/113586936/VRayLight).

For a scene with locked geographical sun studies, keep its original direction/time. Offer compatible colour/intensity variants instead of silently changing the sun to these suggestions.

## Per-preset setup and acceptance

### P00 — Original Scene

Capture the source revision, light nodes/instances, units, values, transforms, animation, environment maps, overrides and VFB state before any experiment. Restore from that record or reopen the preserved baseline copy. Generic V-Ray defaults cannot restore a custom scene. Compare the restored state against the capture before calling it a successful reset.

### P01 — Clear Neutral Daylight

Use for broad building, amenity and pool views. Start from the existing Sun/Sky or coherent daylight rig. Seek separation between sunlit and shaded surfaces without flattening the whole environment. Do not add a second analytic sun over an HDRI containing a strong sun.

An optional diffuse lit-to-shade calibration target is **3:1 (2–4:1)**. Keep facade whites textured and vegetation differentiated. Reject clipped pale facades, electric-green planting or reflections inconsistent with the illumination. [Pavani Mirai, approximately 00:36](https://www.youtube.com/watch?v=LZfvC9NAMjA&t=35s).

### P02 — Dappled Garden Backlight

Use only where existing trees, screens or overhangs can create the pattern. Choose a world-space side/backlight direction for the actual hero view, then keep it consistent through the camera move. Use existing sky illumination to retain depth in shaded foliage.

Suggested diffuse lit-to-shade target: **4:1 (3–5:1)**. Do not plant trees, add shadow cards, move vegetation or paint light shafts. A compatible existing scene is required. Test leaves, thin branches and shadow edges in motion at native 4K. [Encanto, approximately 02:00](https://www.youtube.com/watch?v=1KFbhDrLn-0&t=120s).

### P03 — Golden Low Sun

Use the low-elevation response of the verified physical sky model, with cooler environmental fill. The proposed angle is an authored starting point; the footage does not establish whether a particular shot is dawn or dusk.

Suggested diffuse lit-to-shade target: **6:1 (4–8:1)**. Preserve original stone and timber hue beneath the light. Keep the sun fixed in world space across a connected scene, not glued behind each camera. Added haze is not included. [Presidential Towers, approximately 00:17](https://www.youtube.com/watch?v=Q3zCo73GNu0&t=17s).

### P04 — Soft Window Interior

Use existing luminous windows and sky as the dominant source. Sun elevation and Sun size are deliberately unspecified: soft window light is not reliably created by one universal sun angle or by making the sun enormous. If the original rig produces incompatible hard sunlight, propose and preview a separate lighting change.

Suggested diffuse lit-to-shade target: **2.5:1 (2–3:1)**. Optional existing warm fixtures stay subordinate. Do not alter glazing opacity, curtain transmission, wall albedo or the camera exposure to force this recipe. Keep gradients across pale upholstery and walls. [Encanto, approximately 01:31](https://www.youtube.com/watch?v=1KFbhDrLn-0&t=90s).

### P05 — Warm Raking Interior

Aim the approved existing sun through a real opening so it grazes the intended surface. Existing window orientation and surrounding buildings constrain whether the effect is possible. Retain sky/GI fill and keep selected practicals below the daylight key.

Suggested diffuse lit-to-shade target: **5:1 (4–6:1)**. Reject light through opaque walls, fake volumetric beams or altered material roughness. Check moving sun-patch edges and polished highlights without changing the camera. [Riviera Crown, approximately 01:30](https://www.youtube.com/watch?v=dKymE__UK68&t=90s).

### P06 — Warm Practical Luxury

Separate existing cove, wall-wash, decorative and general fixtures into understandable groups. Keep their actual physical dimensions, units and IES distribution. Calibrate contribution per group; the same numeric multiplier on different fixture types does not mean equivalent illumination.

Suggested diffuse lit-to-shade target: **3:1 (2–4:1)**. Preserve visible light-strip shape, stone texture and dark wood detail. Keep window/environment lighting coherent. This recipe does not add invisible fill lights or edit emissive material parameters; scenes relying on those need a separately reviewed plan. [Riviera Crown, approximately 01:05](https://www.youtube.com/watch?v=dKymE__UK68&t=65s).

### P07 — Blue Hour + Warm Practicals

Use only if the existing environment can produce twilight and the actual fixtures are present. Verify the sky model's below-horizon response. A missing twilight environment is a decision to resolve, not permission to download or substitute an HDRI. Keep background, illumination and reflections consistent.

Suggested diffuse lit-to-shade target: **5:1 (3–8:1)** where comparable diffuse surfaces exist. The suggested 3000 K is for selected architectural fixtures, not every source: preserve intended pool/RGB lighting and separately assess sports floodlights. Reject artificial black skies with daytime reflections or nonexistent glowing fixtures. [Century Mirai, approximately 02:07](https://www.youtube.com/watch?v=tO-Vl1hLa6U&t=127s).

### P08 — Low-Key Material Detail

Use only where the saved camera already shows a suitable detail. Let an existing window or fixture produce a narrow reflected/grazing highlight. Keep its original colour unless an explicit variant is approved. No camera reframing, extra macro shot or material modification is included.

Suggested diffuse lit-to-shade target: **10:1 (8–16:1)** where a meaningful diffuse comparison exists; do not use this ratio to judge a metal or glass specular highlight. Check raw versus denoised texture and avoid crushed shadows or halos. [Century Mirai, approximately 00:38](https://www.youtube.com/watch?v=tO-Vl1hLa6U&t=37s).

### P09 — Theatrical Studio Specialty

This is a separate, non-default family inspired by the Riviera Crown prologue. It is unavailable for an ordinary architectural scene unless that scene already has an appropriate set, object and studio lights. Do not introduce chess pieces, a black backdrop, fog or replacement architecture.

Use existing key/rim sources with a proposed supported-light CCT of 5000 K. Suggested diffuse contrast target: **12:1 (8–16:1)** where measurable. Preserve the object's edges and existing accent colours; do not automatically black out the environment. [Riviera Crown, approximately 00:16](https://www.youtube.com/watch?v=dKymE__UK68&t=15s).

## How to interpret the contrast targets

These ratios are optional calibration guides, not V-Ray light multipliers or values measured from YouTube. Compare equivalent neutral diffuse surfaces, or an appropriate irradiance diagnostic, in scene-linear data before grading. Different albedos, normals, exposure transforms and specular reflections can invalidate a direct pixel comparison. Do not modify scene materials merely to meet a ratio. If a useful comparison is unavailable, leave the number unresolved and judge the pilot visually.

Absolute lumens/watts, source intensities, HDRI output, camera exposure offsets and LUT strengths are intentionally not supplied. They depend on scene scale, fixture units, source size, materials, light transport and the existing colour pipeline. Start from recorded existing values, show proposed changes, then approve the result.

## LightMix, physical relighting and grade are separate

| Change | Route | Approval implication |
| --- | --- | --- |
| Balance existing rendered light intensity/colour | V-Ray LightMix when the required passes exist | Fast look exploration; not a new shadow solution |
| Sun direction, emitter position/size, HDRI orientation or shadow pattern | Native scene lighting and rerender | Requires a new 4K pilot |
| White balance, tone curve, highlight rolloff and selective saturation | Recorded VFB/finishing layers | Does not create missing physical light or detail |

Configure LightMix before the pilot; group mapped lights sensibly and verify all contributors, including environment, self-illumination and Rest where used. Chaos documents saving variants, and warns that strongly amplifying weak contributions can expose noise; reconcile approved changes with the scene and rerender when needed. LightMix is incompatible with Irradiance Map GI: detect a legacy setup and flag it rather than silently changing GI. [Chaos LightMix](https://docs-chaos.atlassian.net/wiki/spaces/VMAX/pages/113578216).

Save the actual grade/layer state and document whether it is baked. VFB layers are not preserved by every EXR output path; Chaos distinguishes V-Ray EXR/VRIMG from the 3ds Max Common EXR route. A LUT alone may omit masks and other layer operations. Verify raw-versus-display parity and apply the display transform once. [Chaos VFB Layers](https://docs-chaos.atlassian.net/wiki/spaces/VMAX/pages/113588521/Layers).

## Safe application on the other workstation

1. Audit the actual scene and exact renderer build/engine there. Do not open or transfer the huge scene onto this PC.
2. Save a versioned working copy and capture P00. Record the existing OCIO/VFB configuration, light units and all source dependencies.
3. Bind the chosen recipe to explicitly identified existing lights. Never auto-select the first Sun or silently create missing nodes. Show unavailable recipes with a reason.
4. Show a parameter diff and proposed world direction. Do not overwrite existing light animation without a separate approval. Geometry, shaders, textures and camera/timing remain locked.
5. Test only relevant recipes on representative native-4K frames, then a short continuous camera section. Compare original, relit-ungraded and relit-graded images. Reduced-size previews cannot approve 4K detail.
6. Approve one version per lighting chapter. Keep physical lighting consistent between connected shots. Do not chase the camera with the sun or auto-correct exposure/white balance per frame.
7. Render every required frame, step 1, at the source FPS and approved 4K raster. Keep lossless EXR masters and original frame mapping; assemble and finish those frames without AI generation, upscaling or interpolation.
8. Validate motion, shadow stability, foliage/specular flicker, noise, texture retention, highlight clipping and colour transforms. Archive scene revision, bindings, approved recipe, grade and QC alongside the master.

No extra atmosphere, flare, depth of field, motion blur, sound or music is introduced by a lighting preset. Existing approved effects are preserved and checked separately. A reference-like result depends on the source assets and a successful render/grade pilot, not just a dropdown choice.

The aashskill and cinematic-lighting guidance shaped this library's separation of physical lighting from grading, world-space continuity rules, reference evidence and fidelity checks. Their suggestions to invent shots, characters or new lighting events were not adopted. See `Native-4K-VRay-Production-Plan.md` for the overall pipeline.
