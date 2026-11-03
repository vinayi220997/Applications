# Vectorforge API

Base URL: wherever the server runs, for example `http://localhost:8000`. Interactive OpenAPI docs are at `/docs` and the raw schema at `/openapi.json`.

Parameter names follow the Vectorizer.AI API, so most existing clients work after you change the base URL and credentials. Requests accept `multipart/form-data`, `application/x-www-form-urlencoded`, JSON bodies, or query parameters.

## Authentication

Off by default. When `VF_API_KEYS` is set, `/api/v1/*` requires one of the keys, sent either as:
- `X-API-Key: <key>`, or
- HTTP Basic with the key as username or password: `curl -u <key>: ...`

The web-app job endpoints (`/api/jobs/*`) are not key-protected, so the browser UI keeps working. Put the whole server behind your own auth proxy if it shouldn't be public.

## REST endpoints

### `POST /api/v1/vectorize`
Vectorize one image and return the file.

Provide the image as exactly one of:

| Field | Description |
|---|---|
| `image` | file upload (PNG, JPG, GIF, BMP, WebP, TIFF, ICO; ≤ 30 MiB) |
| `image.base64` | base64 string; a `data:` URL is accepted too |
| `image.url` | http(s) URL. Private and loopback addresses are refused unless `VF_ALLOW_PRIVATE_URLS=1`. |
| `image.token` | token from an earlier call that set `policy.retention_days` |

Plus `policy.retention_days` (0–30). When it's above 0, the image is kept and an `X-Image-Token` header is returned for later `/download` calls.

Response: the file. Headers: `Content-Disposition` (suggested filename), `X-Image-Token` (when retained), `X-Vectorforge-Shapes`, `X-Vectorforge-Colors`.

```bash
curl -F image=@logo.png -F output.file_format=svg http://localhost:8000/api/v1/vectorize -o logo.svg
curl -F image=@logo.png -F policy.retention_days=1 -D - -o logo.svg http://localhost:8000/api/v1/vectorize
```

### `POST /api/v1/download`
Re-export a retained image (`image.token`, required) with different `output.*` options. Processing options can be changed too; that triggers re-processing.

```bash
curl -F image.token=$TOKEN -F output.file_format=dxf \
     -F output.dxf.compatibility_level=lines_arcs_and_splines \
     http://localhost:8000/api/v1/download -o logo.dxf
```

### `POST /api/v1/delete`
Delete a retained image: `image.token`. Returns `{"success": true}`.

### `GET /api/v1/health`
`{"status": "ok", "version": "1.0.0", "jobs": N}`

### `GET /api/v1/options`
Machine-readable list of every option, with type, default, range and choices.

## Options

### Input and processing (these change the geometry)

| Name | Type | Default | Values |
|---|---|---|---|
| `input.max_pixels` | int | 2097152 | 100 – 6291456. Larger images are downscaled first; output stays in original pixel units. |
| `processing.max_colors` | int | 0 | 0 – 256. 0 means automatic. |
| `processing.palette` | string | – | `#RRGGBB[ -> #RRGGBB\|none][ ~ tol];` entries. Without tolerances the palette is strict and every pixel snaps to the nearest entry, which is then written as its remap colour. With tolerances, automatic colours within `tol` (ΔE) of an entry are replaced by it. `none` makes that colour transparent. |
| `processing.image_type` | enum | auto | `auto`, `art`, `photo` |
| `processing.detail` | enum | medium | `low`, `medium`, `high` (smoothing, smallest region, fit tolerance) |
| `processing.shapes.min_area_px` | float | 0 | regions smaller than this merge into a neighbour (0 = detail default) |
| `processing.fit_tolerance` | float | 0 | max curve fitting error in px (0 = detail default: 0.5 for art, 0.9 for photos) |
| `processing.corner_threshold` | float | 50 | direction change in degrees above which a point is a sharp corner |
| `processing.background.remove` | bool | false | make border-connected background colours transparent |
| `processing.background.tolerance` | float | 12 | colour distance for background detection |
| `processing.parameterized_shapes.enabled` | bool | true | fit whole shapes |
| `processing.parameterizedShapes.ellipse.circle.enabled` | bool | true | |
| `processing.parameterizedShapes.ellipse.general.enabled` | bool | true | |
| `processing.parameterizedShapes.quadrilateral.rectangle.enabled` | bool | true | |
| `processing.parameterizedShapes.quadrilateral.general.enabled` | bool | true | |
| `processing.parameterizedShapes.triangle.general.enabled` | bool | true | |
| `processing.parameterizedShapes.star.enabled` | bool | true | regular stars with 3–6 points |
| `output.shape_stacking` | enum | cutouts | `cutouts` (no overlaps) or `stacked` (shapes drawn over each other, no seams) |
| `output.curves.allowed.*` | bool | true | `circular_arc`, `cubic_bezier`, `quadratic_bezier`. These limit both fitting and output; a disallowed type is converted on export. |

### Output (export only, no re-processing)

| Name | Type | Default | Values |
|---|---|---|---|
| `output.file_format` | enum | svg | `svg`, `pdf`, `eps`, `dxf`, `png` |
| `output.group_by` | enum | none | `none`, `color` |
| `output.draw_style` | enum | fill_shapes | `fill_shapes`, `stroke_shapes`, `stroke_edges` |
| `output.strokes.stroke_width` | float | 1 | 0 – 20 |
| `output.strokes.non_scaling_stroke` | bool | true | |
| `output.strokes.use_override_color` / `output.strokes.override_color` | bool / color | false / #000000 | |
| `output.gap_filler.enabled` | bool | true | same-colour strokes under the fills hide anti-aliasing seams |
| `output.gap_filler.stroke_width` | float | 1.5 | 0 – 5 |
| `output.gap_filler.non_scaling_stroke` | bool | true | |
| `output.parameterized_shapes.flatten` | bool | false | write circles, rects and polygons as paths |
| `output.curves.line_fit_tolerance` | float | 0.1 | error when curves are flattened into lines |
| `output.svg.version` | enum | svg_1_1 | `svg_1_0`, `svg_1_1`, `svg_tiny_1_2` |
| `output.svg.fixed_size` | bool | false | write width/height attributes |
| `output.svg.adobe_compatibility_mode` | bool | false | no `vector-effect`; scaling strokes |
| `output.pdf.compression_mode` | enum | Deflate | `None`, `Deflate` |
| `output.dxf.compatibility_level` | enum | lines_and_arcs | `lines_only`, `lines_and_arcs` (bulged polylines), `lines_arcs_and_splines` |
| `output.bitmap.anti_aliasing_mode` | enum | anti_aliased | `anti_aliased`, `aliased` |
| `output.size.scale` | float | – | uniform scale factor |
| `output.size.width`, `output.size.height` | float | – | target size in `output.size.unit` |
| `output.size.unit` | enum | none | `none`, `px`, `pt`, `in`, `cm`, `mm` |
| `output.size.aspect_ratio` | enum | preserve_inset | `preserve_inset`, `preserve_overflow`, `stretch` |
| `output.size.align_x`, `output.size.align_y` | float | 0.5 | 0 – 1 |
| `output.size.input_dpi`, `output.size.output_dpi` | float | – | override detected DPI / PNG output DPI |

## Web-app job API

Used by the browser UI. It's also handy for long-running or interactive clients.

| Method and path | Description |
|---|---|
| `POST /api/jobs` | multipart `image` (or `image.url`/`image.base64`) plus `options` (JSON object of processing options). Returns `202` with the job summary and its `token`. |
| `GET /api/jobs/{token}/events` | Server-Sent Events: `progress` events (`stage`: decoding, palette, segmenting, tracing; `progress` 0–1), then `done` with palette and stats, or `error`. |
| `GET /api/jobs/{token}` | current summary (same JSON as the events) |
| `POST /api/jobs/{token}/reprocess` | JSON body of processing options to change. Starts a new revision; listen to `events` again. |
| `GET /api/jobs/{token}/result?output.file_format=…&download=1` | export with any `output.*` query options. Inline by default, attachment with `download=1`. |
| `GET /api/jobs/{token}/source` | the original upload |
| `DELETE /api/jobs/{token}` | delete the job and its files |

Summary JSON (`done`):

```json
{
  "token": "1793643128590-446f3c28eaa9e505e46599ed",
  "status": "done", "stage": "done", "progress": 1.0, "revision": 1,
  "filename": "logo.png", "width": 400, "height": 300,
  "palette": [{"index": 0, "source": "#ffffff", "color": "#ffffff", "coverage": 0.664}],
  "stats": {"image_type": "art", "colors": 4, "shapes": 4, "nodes": 22,
            "primitives": {"circle": 1, "triangle": 1},
            "segments": {"L": 18, "A": 4}, "timings_s": {"total": 0.46}}
}
```

## Errors

Every error returns `{"error": {"status": <http>, "code": <int>, "message": "..."}}`.

| HTTP | Code | Meaning |
|---|---|---|
| 400 | 1005 | no image given |
| 400 | 1006 | image could not be decoded |
| 400 | 1016 | `image` was sent as text instead of a file |
| 400 | 1019 | invalid option (message names it) |
| 400 | 1020 / 1021 / 1022 / 1024 | URL returned non-200, a non-image, failed, or was refused |
| 400 | 1023 | requested PNG output larger than 52 MP |
| 400 | 1027 | image token not found or expired |
| 401 | 1004 | missing or invalid API key |
| 409 | 2001 | result requested while still processing |
| 413 | 1012 | file larger than 30 MiB |
| 413 | 1013 | image larger than 32 MP decoded |
| 429 | 1015 | rate limit exceeded |
| 500 | 2000 | unexpected internal error |
