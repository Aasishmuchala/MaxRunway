# MaxRunway 0.2.0

3ds Max 2026 · V-Ray 7.x · Windows

**Experimental preview.** Download the installable ZIP from this repository's Releases page. Standalone Runway authentication/generation, live Omega Plus requests, and exact V-Ray 7.2 compatibility remain unverified; see `VALIDATION.md` before production use.

MaxRunway captures native V-Ray references, sends a separate cinematic request through Runway's generation MCP, and compares the downloaded result against the native frames. It is a scripted production panel, not a replacement renderer and not a guarantee that a generative model preserved V-Ray materials.

## Install

The packaged release contains an Autodesk Application Plug-in bundle.

1. Extract the ZIP completely.
2. Right-click `Install.ps1` and run it with PowerShell. Administrator access is not required.
3. Restart 3ds Max 2026. The MaxRunway panel opens after startup.
4. Keep Node.js 20.19+ and FFmpeg/FFprobe on `PATH`.

The installer checks every bundled file against `MANIFEST.sha256`, then copies `MaxRunway.bundle` to `%APPDATA%\Autodesk\ApplicationPlugins`. A previous installation is retained as a timestamped backup. `Uninstall.ps1` moves the installed bundle to a recoverable folder and leaves settings and credentials intact.

For a portable copy, keep this source folder together, run `Setup.ps1`, then use **3ds Max → Scripting → Run Script → Launch_MaxRunway.ms**.

## Recommended shot workflow

Choose **Full-rate 640×360 camera guide + sparse V-Ray 4K anchors**.

- Set a whole 4–15 second keyed span. At 24 fps, a ten-second circle is frames **0–240 inclusive**, producing 241 camera poses.
- Keep the default eight 4K anchors. A loop distributes them at 0°, 45°, 90°, 135°, 180°, 225°, 270°, and 315° relative to the animated span, omitting the duplicate closing pose.
- The plugin renders every camera pose at 640×360 through the active V-Ray renderer for authoritative motion, then renders only the sparse appearance anchors at 3840×2160.
- Review the full-rate guide and every 4K anchor before enabling submission.
- Submission uploads the guide and all anchors. The generated prompt declares Video 1 authoritative for camera motion and treats the images only as appearance evidence for the same unchanged scene.
- The live Runway MCP tool schema is checked for image and video reference arrays before any upload or paid generation. If the connected schema does not expose both, submission stops.

This is the strongest tested generative route from the orbit experiment; it improved motion substantially but still failed exact camera closure and appearance fidelity. It is therefore a candidate-generation workflow, not the native master.

Other workflows remain available:

| Workflow | Native capture | Cloud result |
|---|---|---|
| Guided sparse 4K | Every pose at 640×360 + 2–9 native 4K anchors | Seedance 2, explicit 4K candidate |
| Animate one frame | One native 4K EXR + display PNG | 4–15 second 4K animation |
| Full native sequence → variation | Every frame at native 4K | 4–15 second 4K interpretation |
| Native sequence only | Every frame at native 4K | No cloud request |

## Connections and settings

### Direct Runway generation

**Connect Runway (browser sign-in)** uses the bundled MCP client and a separate Runway OAuth cache under `%LOCALAPPDATA%\MaxRunway\mcp-auth`. Connection checks do not create media. **Send to Runway** does create a paid generation, and the panel labels it accordingly.

### ChatGPT through Codex

The panel locates the installed Codex client. **Sign in** launches the supported `codex login` flow; **Check ChatGPT login** runs `codex login status`. MaxRunway never reads or copies the resulting account token. ChatGPT/Codex is used only for visual quality analysis.

### Codex-managed Runway MCP

The default server name is `runway` and the default endpoint is `https://mcp.runwayml.com/mcp`. **Configure / sign in** adds the HTTPS endpoint to the user's Codex MCP configuration when missing, then launches `codex mcp login runway`. This is an additional managed connection/status path. The deterministic generation adapter still uses its own direct Runway login, so one route cannot silently borrow the other's private OAuth material.

### Omega Plus Vision

The default endpoint is `https://api.omegaplusapi.com/v1/chat/completions`; the model ID is editable and defaults to `omega-plus`. The bundled list reflects the provider's model catalogue retrieved on 14 September 2026. **Save key securely** writes the API key to Windows Credential Manager under `MaxRunway/OmegaPlusApiKey`; it is never written to plugin settings or a `.max` scene.

The linked Omega Plus documentation exposes OpenAI-compatible chat/vision input. It does not publish `/v1/images` or an image-generation endpoint, so MaxRunway labels this integration **Omega Plus Vision** and does not claim image generation. **Test vision API** sends a tiny provider request only when the user clicks it.

## AI analysis and final gate

After a generated video downloads, choose ChatGPT/Codex or Omega Plus Vision and click **Analyze downloaded video against native V-Ray**.

The worker extracts four matching points across the shot and creates side-by-side JPEG evidence: native V-Ray on the left, generated output on the right. The provider returns bounded 0–100 scores for geometry, materials, lighting, colour, and motion continuity, plus findings and a visual verdict.

The result is saved to `analysis/<provider>-analysis.json`. The final gate is deliberately strict:

- Output dimensions and duration can pass.
- Visible review can report similar, changed, or unusable.
- `materialFidelityGuaranteed` remains `false`.
- A visually similar result becomes `manual_material_review_required`, never an automatic perfect pass.
- Any material, geometry, or motion problem becomes `failed`.

Pixel comparison cannot prove that V-Ray shaders, UVs, source textures, geometry, LightMix, render elements, or view-dependent reflection data survived generation. Use the native EXR sequence for shots that require exact truth.

## Native output and isolation

Each job gets a new immutable folder:

```text
job.json
master/                         sparse or full native 4K EXR files
preview/                        reviewed PNGs and guide/review MP4
guide/master/                   full-rate 640×360 EXRs for guided jobs
guide/preview/                  full-rate guide PNGs
elements/ and guide/elements/   redirected render-element destinations
runway/cinematic_4k.mp4         separate generated candidate
analysis/                       comparison evidence and structured QC
```

Existing V-Ray raw/split output flags and render-element filenames are temporarily redirected or disabled and then restored. Materials, textures, lights, animation, and the scene file are not rewritten or saved. Missing external assets or UVs abort rendering. Every native frame is hashed; changed or incomplete sources block submission.

EXRs are saved without output colour conversion. Review PNGs use 3ds Max automatic file-output conversion. The actual EXR channel precision/compression and VFB/OCIO behaviour remain controlled by the installed 3ds Max/V-Ray configuration and must be verified on the production workstation.

## Lighting recipes

The panel includes the authored IMPACT-inspired lighting library built from the agreed latest five channel uploads. These are visual starting recipes, not recovered studio presets. They are read-only and never auto-apply, create a light, edit a material, or relight a scene. Open the full guide from the panel, bind a chosen recipe to an audited existing rig, and approve a native 4K pilot before rendering a chapter.

## Recovery

The job records its cloud task ID before polling. If a connection fails after a task may have been charged but before an ID is known, automatic resubmission is disabled. Check Runway history first. A known task can be attached with:

```powershell
node bridge/cli.mjs resume "C:\path\to\job.json" "existing-runway-task-id"
```

Closing the panel hides it; it does not orphan the current process. Closing 3ds Max does not cancel a submitted cloud task.

## Verification

```powershell
python -m unittest discover -s tests -v
npm.cmd --prefix bridge test
```

See `VALIDATION.md` and `SECURITY.md`. The release is smoke-tested on 3ds Max 2026.2 with installed V-Ray 7.30.02. V-Ray 7.2 is the compatibility target requested by the user, but that exact build is not installed on the development machine and must be checked on the destination PC.

## References

- [Autodesk 3ds Max application plug-in packages](https://help.autodesk.com/cloudhelp/2026/ENU/MAXDEV-Developer/files/writing_plug-ins/plugin_package.html)
- [Autodesk package XML format](https://help.autodesk.com/cloudhelp/2026/ENU/MAXDEV-Developer/files/writing_plug-ins/plugin_package/packagexml_format.html)
- [Autodesk renderer control](https://help.autodesk.com/cloudhelp/2026/ENU/MAXScript-Help/files/MAXScript-Tools-and-Interaction/Interacting-with-the-3ds-Max/Render-Scene-Dialog/GUID-9175301C-13E6-488B-ABA6-D27CD804B205.html)
- [Runway Seedance 2.0 input guidance](https://help.runwayml.com/hc/en-us/articles/50488490233363-Creating-with-Seedance-2-0)
- [Runway input requirements](https://docs.dev.runwayml.com/assets/inputs/)
- [Runway generation MCP](https://mcp.runwayml.com/)
- [Omega Plus API documentation](https://omegaplusapi.com/customer/docs)
