# Face recognition

Everything here runs locally on the CPU. No image is ever sent to a
third-party service, and there is no paid API in the pipeline.

## How a match happens

```
Photo uploaded
   -> decoded and downscaled to 1920px for detection
   -> SCRFD finds each face and its 5 landmarks
   -> each face aligned to a 112x112 crop
   -> ArcFace turns the crop into a 512-number vector
   -> vector stored in `faces`, tagged with photo_id and event_id

Guest selfie
   -> same detection and embedding
   -> compared against faces WHERE event_id = this event
   -> cosine similarity per face, best score kept per photo
   -> photos scoring above FACE_MATCH_THRESHOLD returned, best first
```

Embeddings are unit length, so cosine similarity is a plain dot product and
lands between -1 and 1. Identical people score high; unrelated people score
near zero.

## Why these models

The default engine runs the InsightFace `buffalo_l` ONNX models **directly
through onnxruntime**, rather than installing the `insightface` package.

That is a deliberate choice. `insightface`, `dlib` and `face_recognition` all
need a C toolchain — on Windows that means Visual Studio Build Tools, which is
a large and frequent obstacle. `onnxruntime` and `opencv-python` ship prebuilt
wheels for Windows, macOS and Linux, so `pip install -r requirements.txt` works
with no compiler. The models are the same ones the package would use.

The detector's five landmarks feed the recogniser's alignment step, so the two
fit together without a third landmark model.

## Engines

| | `arcface` (default) | `opencv` |
|---|---|---|
| Detector | SCRFD | YuNet |
| Recogniser | ArcFace (`w600k_r50`) | SFace |
| Dimensions | 512 | 128 |
| Download | ~190 MB | ~39 MB |
| Accuracy | Higher | Lower |
| Suggested threshold | `0.38` | `0.30` |

Switch with `FACE_ENGINE=opencv` in `.env`, then:

```bash
python -m app.face.download --engine opencv
```

A smaller ArcFace pack also exists for low-powered servers:

```bash
python -m app.face.download --pack buffalo_s
```

> **Switching engines changes the vector width**, so existing embeddings become
> unusable. On PostgreSQL the `faces.embedding` column is sized from
> `EMBEDDING_DIM`, so re-run migrations and reprocess:
> ```bash
> alembic downgrade base && alembic upgrade head
> ```
> then re-upload, or clear the `faces` table and use the reprocess endpoint.

## Choosing a threshold

`FACE_MATCH_THRESHOLD` is the cosine similarity a face must reach to count as
a match. There is no universally right value — it is a trade between guests
who find nothing and guests who get sent a stranger's photos.

| Value | Behaviour |
|---|---|
| `0.30` | Very inclusive. Good for dim receptions and profile shots; expect occasional wrong matches. |
| `0.38` | **Default.** Reliable recall in mixed event lighting. |
| `0.50` | Conservative. Few wrong matches, misses harder shots. |
| `0.55`+ | High precision. Will miss profile shots and motion blur. |

### Why the default is 0.38, not 0.55

Measured on this pipeline with real photographs, using a deliberately degraded
"phone selfie" (scaled to 240px, brightened, tilted 8°, JPEG quality 40):

| Comparison | Score |
|---|---|
| Same person, degraded selfie vs. solo portrait | **0.74** |
| Same person, degraded selfie vs. group photo | **0.74** |
| Different person | **≈0.00** |
| Photo containing no people | no faces detected |

The gap between a correct match and a wrong one is enormous, so the threshold
has plenty of room. But real events are harder than test images — guests are
turned away from the camera, moving, backlit, or half behind someone else. A
threshold of `0.55` sits close enough to genuine matches that those harder
frames silently disappear, and a guest who was photographed all night is told
there are no photos of them. `0.38` keeps a wide safety margin against false
matches while surviving bad conditions.

Reproduce these numbers yourself:

```bash
python -m app.face.download
pytest tests/test_face_engine.py -v
```

### Tuning on your own event

Threshold changes apply to new searches immediately — no reprocessing needed,
because it filters stored vectors rather than changing them.

1. Upload a set of photos from a real event.
2. Search with a selfie of someone you can identify in them.
3. Too few results, lower it by `0.03`. Wrong people appearing, raise it.

## Other settings

| Setting | Default | Effect |
|---|---|---|
| `FACE_DETECT_SIZE` | `640` | Detector input size. `800` finds smaller faces at more CPU cost. |
| `FACE_DETECT_THRESHOLD` | `0.5` | Confidence needed to call something a face. |
| `FACE_MIN_SIZE` | `32` | Faces smaller than this many pixels are ignored. Raise it at large venues so distant crowds aren't indexed. |
| `FACE_MAX_RESULTS` | `300` | Cap on photos returned per search. |
| `WORKER_CONCURRENCY` | `2` | Face-processing threads. Roughly one per two cores. |

## Selfie rules

A selfie must contain **exactly one** face. Zero gets `NO_FACE`; more than one
gets `MULTIPLE_FACES`, because with two faces there is no way to know which
person is searching.

`FACE_MIN_SIZE` decides this in practice: a small bystander in the background
falls below it and is ignored, so a guest isn't blocked by someone walking past
behind them. Raise it if guests report the "only you" message unfairly.

## Performance

Rough figures on a modern 4-core CPU, per photo:

| Step | Time |
|---|---|
| Thumbnail | ~40 ms |
| Detection (640px) | ~120 ms |
| Embedding per face | ~35 ms |

A typical 3-face photo is around a quarter of a second per worker. Uploading
never waits on any of this — the request returns once files are written, and
detection happens on the background queue.

Search stays fast as events grow: pgvector's HNSW index is queried with an
`event_id` filter, so an event with 5,000 photos is not scanning the whole
table.
