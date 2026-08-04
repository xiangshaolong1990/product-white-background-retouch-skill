# Lens AI Reflection Repair

For eyewear white-background retouching, lens inspection is mandatory but AI repair is conditional. If the original lens is already clean and naturally graded, preserve its pixels exactly and do not create a repair mask. Remove only identified reflected objects, studio glare, scratches, or other visible defects while preserving real temple arms, hinges, nose pads, and hardware visible through the lenses.

Treat the source lens colour and natural tint map as immutable. The repair model may interpolate across a defect but may not reinterpret or re-grade the lens.

## Boundary Rules

1. Use a small feathered mask for each isolated unnatural reflection or defect. Do not use a complete lens-interior mask unless the user explicitly requests a full lens re-grade.
2. Keep the mask safely inside the visible lens edge.
3. Feather the mask 4-8 pixels at full resolution.
4. Exclude the frame, bridge, hinges, nose pads, logos, and printed text. Avoid broad cut-out holes around translucent temple regions because they can create visible gradient seams; preserve temple geometry through the edit prompt and visual QA.
5. Keep the source image and the non-generative white-background retouch as references.
6. Every repair mask must correspond to a visible, named defect. No defect means no mask and no AI edit.

## Final-Only Workflow

Keep all working files in a temporary directory. First prepare a padded local crop:

```bash
python3 "$SKILL_ROOT/scripts/lens_repair_workflow.py" prepare \
  --input "$TEMP_WHITE_IMAGE" \
  --polygons "x1,y1 x2,y2 x3,y3 x4,y4" \
  --work-dir "$TEMP_LENS_DIR"
```

Use built-in `$imagegen` with only `$TEMP_LENS_DIR/input.png` as the visual target. Describe the defective reflection precisely in the prompt. Do not attach `mask.png` as a second visual reference: some generative models may reproduce the mask as a dark shape. The mask remains authoritative during the deterministic composite. Use medium quality first.

If an approved same-product lens reference is available, attach it after `input.png` and state that the first image is the only edit target. Use the reference only for the clean tint gradient and blemish-free finish; never transfer its crop, scale, frame shape, logo placement, or temple geometry.

Composite the AI crop back through the original full-resolution mask:

```bash
python3 "$SKILL_ROOT/scripts/lens_repair_workflow.py" composite \
  --input "$TEMP_WHITE_IMAGE" \
  --manifest "$TEMP_LENS_DIR/manifest.json" \
  --protect-mask "$OPTIONAL_STRUCTURE_PROTECT_MASK" \
  --ai-result "$AI_RESULT" \
  --output "$FINAL_OUTPUT"
```

Never deliver the raw AI crop or the raw full-image AI edit.

`--protect-mask` is optional. Its white pixels are restored from the approved source after the repair mask is applied. Keep it tight to real rims, temples, hinges, logos, or printed marks; broad protection areas can reintroduce the reflection being removed.

## Edit Instruction

Use this instruction with the available image-editing model:

```text
Retouch this exact local lens crop. Remove only the specifically identified unnatural reflection, glare streak, scratch, or blemish. Copy and interpolate the immediately adjacent original lens pixels across that defect. Do not re-grade or rebuild the complete lens. Preserve the original lens colour, tint density, transparency, natural gradient, temple perspective, frame, rim, bridge, logo, crop, scale, and geometry. The repaired patch must have no visible boundary or colour shift.
```

## Composite and QA

Composite only the repaired patch through the feathered full-resolution mask onto the approved white-background retouch. Treat the left and right lenses as separate repair jobs, then reinspect both at full-image scale and close-up scale after each composite.

After any AI composite, perform a mandatory second inspection at 200% or closer. A thin arc, vertical reflection line, duplicated arm contour, cloudy patch, glare spot, studio silhouette, scratch, or uneven band means the lens is still unfinished. Prepare a smaller residual-defect mask and run a second AI pass while using the original source to distinguish true through-lens structures from surface reflections.

Reject the patch if it changes lens colour, tint density, transparency, or natural gradient; blurs the lens edge; alters the bridge or frame; changes a logo; leaves optical glare; removes or shifts a real temple; or creates any visible boundary, colour block, cloudy band, white patch, or abrupt transition.
