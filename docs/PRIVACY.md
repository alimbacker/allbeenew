# Privacy

Guests hand over a photograph of their face to find their photos. That deserves
care, so this document states plainly what is held, where, and for how long.

## What is collected

| Data | Why | Where |
|---|---|---|
| The selfie a guest submits | To find their photos | `storage/events/{code}/selfies/` |
| A 512-number face vector per detected face | Comparing faces | `faces.embedding` |
| Which photos matched, and the score | Showing results again without re-uploading | `photo_matches` |
| A timestamp per search | Counting guests | `guest_searches` |

## What is not collected

No name, no email, no phone number, no address, no account. Guests are never
asked to identify themselves, and the system has no field to store it in.

There is no analytics script, no advertising pixel and no third-party
JavaScript anywhere in the guest pages. Fonts are served from your own server,
not from Google.

## Where processing happens

Face detection and matching run on **your own server's CPU**, using models
downloaded once and stored locally. No image, and no face vector, is ever sent
to an outside service. There is no cloud recognition API in the pipeline.

## Isolation between events

Every search is filtered by `faces.event_id`, and the event is resolved from
the code the guest arrived with. A guest at one wedding cannot reach, search,
or appear in results from any other event — including events belonging to a
different photographer. This is enforced in the query itself rather than by a
check that could be forgotten, and is covered by tests.

## The photographer is in control

The photographer who owns an event can, at any time:

- **Close the guest link** — the gallery, searches and photo delivery all stop
  responding immediately.
- **Delete individual photos** — the file, its thumbnail and its face vectors go
  together.
- **Delete the whole event** — every row and the entire storage directory.

## Retention

`GUEST_DATA_RETENTION_DAYS` controls how long guest selfies and search history
are kept.

```ini
# 0 = keep indefinitely (the default; nothing is ever deleted automatically)
GUEST_DATA_RETENTION_DAYS=0
```

The default is deliberate: silently deleting a photographer's data would be
worse than keeping it. Set a value and photographers can hold guest data only
as long as it is useful. Individual events can also override it via
`retention_days`.

A sensible policy for most photographers is 30 days: long enough for a guest to
come back for their photos, short enough that selfies are not kept forever.

Note that this covers **guest** data. Event photos themselves are never removed
by retention — those are the photographer's work product, and deleting them is
always an explicit action.

## What guests are told

The selfie page states, before anything is submitted, that the selfie is used
to find photos at this event only, that face data is processed for matching,
that the photographer controls the event, and that no personal details are
collected. It is written in plain language, not as a legal notice.

## If you are subject to GDPR or similar law

This document describes the system, not your legal position. A few things worth
knowing before an event:

- A face vector is **biometric data** in the GDPR sense, which is a special
  category with a higher bar for lawful processing. You will usually be relying
  on explicit consent.
- The photographer, not ALLBEE, is the data controller. Get advice suited to
  your jurisdiction and your contract with the venue or couple.
- Set a retention period rather than leaving it at `0`.
- Be ready to answer deletion requests — deleting the event, or the relevant
  photos, removes the associated face vectors through the database cascade.
