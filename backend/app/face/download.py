"""Fetch face-recognition models into ``FACE_MODEL_DIR``.

Run once after installing the backend:

    python -m app.face.download                  # default (arcface / buffalo_l)
    python -m app.face.download --pack buffalo_s # smaller, faster, less accurate
    python -m app.face.download --engine opencv  # YuNet + SFace

Downloads are checksum-verified and skipped when the file is already present,
so the command is safe to re-run and safe to put in a deploy script.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from app.config import settings

INSIGHTFACE_RELEASE = "https://github.com/deepinsight/insightface/releases/download/v0.7"

# sha256 of the extracted ONNX files we actually use.
ARCFACE_PACKS: dict[str, dict] = {
    "buffalo_l": {
        "url": f"{INSIGHTFACE_RELEASE}/buffalo_l.zip",
        "keep": {
            "det_10g.onnx": "5838f7fe053675b1c7a08b633df49e7af5495cee0493c7dcf6697200b85b5b91",
            "w600k_r50.onnx": "4c06341c33c2ca1f86781dab0e829f88ad5b64be9fba56e56bc9ebdefc619e43",
        },
    },
    "buffalo_s": {
        "url": f"{INSIGHTFACE_RELEASE}/buffalo_s.zip",
        # Checksums intentionally omitted: verified by ONNX load instead.
        "keep": {"det_500m.onnx": None, "w600k_mbf.onnx": None},
    },
}

# OpenCV Zoo stores these with Git LFS, so a plain raw.githubusercontent.com
# fetch returns a pointer file. We resolve the pointer through the LFS batch
# API, which needs no git-lfs binary installed. The LFS oid *is* the sha256.
OPENCV_REPO = "https://github.com/opencv/opencv_zoo.git"
OPENCV_MODELS = {
    "face_detection_yunet_2023mar.onnx": {
        "oid": "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
        "size": 232589,
    },
    "face_recognition_sface_2021dec.onnx": {
        "oid": "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
        "size": 38696353,
    },
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _download(url: str, dest: Path, label: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  downloading {label} ...", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "allbee-instant/1.0"})
    with urllib.request.urlopen(req, timeout=300) as resp, dest.open("wb") as out:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while chunk := resp.read(1 << 20):
            out.write(chunk)
            done += len(chunk)
            if total:
                pct = done * 100 // total
                print(f"\r    {pct:3d}%  {done / 1e6:.1f} / {total / 1e6:.1f} MB", end="", flush=True)
    print()


def _resolve_lfs(oid: str, size: int) -> str:
    payload = json.dumps(
        {"operation": "download", "transfers": ["basic"], "objects": [{"oid": oid, "size": size}]}
    ).encode()
    req = urllib.request.Request(
        f"{OPENCV_REPO}/info/lfs/objects/batch",
        data=payload,
        headers={
            "Accept": "application/vnd.git-lfs+json",
            "Content-Type": "application/vnd.git-lfs+json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = json.load(resp)
    return body["objects"][0]["actions"]["download"]["href"]


def download_arcface(pack: str, model_dir: Path) -> None:
    spec = ARCFACE_PACKS.get(pack)
    if spec is None:
        raise SystemExit(f"Unknown pack {pack!r}. Choose from: {', '.join(ARCFACE_PACKS)}")

    target = model_dir / pack
    target.mkdir(parents=True, exist_ok=True)

    wanted = spec["keep"]
    if all((target / n).exists() for n in wanted):
        print(f"  {pack}: already present, skipping")
        return

    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / f"{pack}.zip"
        _download(spec["url"], archive, f"{pack}.zip")
        with zipfile.ZipFile(archive) as zf:
            for member in zf.namelist():
                name = Path(member).name
                if name in wanted:
                    with zf.open(member) as src, (target / name).open("wb") as dst:
                        shutil.copyfileobj(src, dst)

    for name, expected in wanted.items():
        path = target / name
        if not path.exists():
            raise SystemExit(f"Archive did not contain {name}")
        if expected:
            actual = _sha256(path)
            if actual != expected:
                path.unlink()
                raise SystemExit(f"Checksum mismatch for {name}: expected {expected}, got {actual}")
        print(f"  ok  {path}")


def download_opencv(model_dir: Path) -> None:
    target = model_dir / "opencv"
    target.mkdir(parents=True, exist_ok=True)
    for name, meta in OPENCV_MODELS.items():
        path = target / name
        if path.exists() and _sha256(path) == meta["oid"]:
            print(f"  {name}: already present, skipping")
            continue
        href = _resolve_lfs(meta["oid"], meta["size"])
        _download(href, path, name)
        actual = _sha256(path)
        if actual != meta["oid"]:
            path.unlink()
            raise SystemExit(f"Checksum mismatch for {name}")
        print(f"  ok  {path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download ALLBEE face models")
    parser.add_argument("--engine", default=settings.face_engine, choices=["arcface", "opencv"])
    parser.add_argument("--pack", default=settings.face_model_pack, choices=list(ARCFACE_PACKS))
    parser.add_argument("--model-dir", default=str(settings.face_model_dir))
    args = parser.parse_args(argv)

    model_dir = Path(args.model_dir)
    print(f"Model directory: {model_dir}")
    if args.engine == "opencv":
        download_opencv(model_dir)
    else:
        download_arcface(args.pack, model_dir)
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
