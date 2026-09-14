# Validation — MaxRunway 0.2.0 — 2026-09-14

## Verified on this machine

- **3ds Max 2026.2**, build `28.2.0.20659`, embedded Python **3.11.12**.
- Installed V-Ray reports **7.30.02**, class `V_Ray_7__update_3_DR2`. The requested V-Ray **7.2** is not installed here, so that exact version is not certified.
- A new, isolated procedural test scene rendered through V-Ray CPU using the plugin's export interface. The test used a checker material and reflective teapot. No user scene was opened or changed.
- Produced an **EXR and PNG at 3840×2160**. FFprobe identified the EXR as floating-point RGBA with **16-bit half-float channels**, using this installation's current EXR writer configuration. The recorded rendering colour space was **ACEScg**.
- The test confirmed that the V-Ray output properties were restored after export, that the camera was discovered, and that the PySide6 panel constructed successfully inside Max. The panel screenshot was visually inspected.
- A real **3840×2160 H.264** review clip was encoded from the test PNGs through the companion. Resolution, **2 fps**, and **1 second** duration were verified with FFprobe. This was a media-path test, not a cinematic quality example.
- Source-hash verification and `prepare` were executed against the actual V-Ray output.
- **20 Node tests** and **16 Python tests** passed. They exercise native/AI separation, full source duration, guided full-rate pose and sparse-anchor contracts, loop/non-loop anchor placement, live-schema rejection before upload, invalid inputs, unique export paths, source mutation detection, saved task IDs, resume without duplicate generation, uncertain submissions, remote failures, secure settings, and resolution/duration checks.
- `npm audit --omit=dev` reported **0 vulnerabilities** for the pinned installed dependency set at the time of testing.
- The connected **Codex Runway MCP** authenticated successfully and reported the chosen 4K-capable model as available. This confirms the account/connector route, not the standalone plugin's separate OAuth session.
- The 0.2.0 panel constructed successfully inside 3ds Max 2026.2 with the guided workflow, IMPACT-inspired read-only lighting library, ChatGPT/Codex settings, Codex-managed Runway MCP settings, and Omega Plus Vision settings. Windows Credential Manager completed a write/read/delete round-trip with a disposable non-secret test value.
- `codex login status` returned **Logged in using ChatGPT**. The packaged analysis worker then inspected the earlier full-rate 4K orbit output through Codex, generated four paired evidence frames, and correctly returned `failed`: delivery resolution/timing passed, but motion continuity scored 24/100 and the orbit mismatch made the shot unusable. Material fidelity remained unverified.
- The release bundle loaded through 3ds Max's `ADSK_APPLICATION_PLUGINS` package scanner, imported its Python module from the staged `MaxRunway.bundle`, and created the panel. The per-user installer and recoverable uninstaller completed a round-trip against an isolated test `APPDATA`. The package manifest verified 4,148 files, and a credential-pattern scan outside third-party dependencies found no packaged secret.

## Remaining validation

Additional native integration evidence: the courtyard fixture produced CPU and GPU 3840×2160 float32 ZIP EXRs after explicitly configuring the EXR writer. Three lighting states were exercised with geometry/material/camera parameter checks and exact baseline-light restoration. Its 48-frame run was stopped after six completed frames when the user changed to a sparse-reference Seedance workflow. The separate orbit test rendered 241 native 640×360 poses and reused eight native 4K anchors; that tested strategy is implemented in the 0.2.0 guided job contract. The newly integrated standalone paid submission was not repeated.

- Standalone plugin browser OAuth must complete its callback. The initial connection attempt timed out after browser sign-in; the plugin has not yet been proven authenticated end-to-end.
- The live standalone generation MCP schema could not be re-read because that OAuth connection timed out. Guided submission therefore checks for both `referenceImages` and `referenceVideos` at runtime and stops before uploading or spending credits when either is absent.
- Omega Plus Vision request construction is covered by local validation and secure credential transport, but no live request was made because no Omega API key was provided. The provider documentation did not expose an image-generation endpoint.
- One paid generation was completed through the **Codex Runway connector**, using eight genuine V-Ray views of the synthetic orbit scene. The original returned file is 3840×2160, 10-bit HEVC, 24 FPS, 241 frames / 10.041667 seconds. The scene-preservation test failed on camera continuity/closure and a changed roof numeral. See the sibling `Orbit-Fidelity-Test/RESULT.md`. This validates that connector route, **not** the standalone panel's OAuth/upload/generation path. The standalone submit/poll/download logic remains covered by controlled-response tests, not this live UI test.
- No claim is made about exact material consistency, V-Ray 7.2, custom VFB grading/LightMix/denoiser parity, custom OCIO configurations, deep EXR, cryptomatte completeness, or long/multi-shot AI continuity. V-Ray GPU was exercised in the separate native fixture, not through the complete 0.2.0 guided submission.
- The synthetic native test establishes that export works; it does not establish production-render quality or a material-preservation score.

## Next real-shot check

Open one production scene, render a reviewed reference, complete the standalone Runway connection, and submit a short shot from the panel. Compare fine textures, window mullions, grout, edges, reflections, colour/exposure, and camera timing against the retained native output. Keep native V-Ray frames as the final master wherever exact geometry and material appearance are required.
