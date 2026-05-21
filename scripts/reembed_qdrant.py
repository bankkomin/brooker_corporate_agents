"""Re-embed all Qdrant points with a new embedder, into {name}_v2 collections.

Use case: switching from Gemini text-embedding-001 (3072 dim) to
google/embeddinggemma-300m (768 dim) without losing the existing corpus.
The old collections stay intact during the migration; only after a clean
cutover do you swap aliases or rename.

Inputs:
  --qdrant-url   Qdrant REST endpoint (default http://localhost:6333)
  --embed-url    OpenAI-compat /embeddings endpoint (default http://localhost:8765/v1)
  --suffix       Suffix for the new collection name (default "_v2")
  --batch        Points per scroll + embed batch (default 64)
  --collections  Comma-separated list, or "all" to discover all live ones

Behaviour:
  - Per source collection:
      1. Discover vector size + distance (from old collection)
      2. Create {name}{suffix} if missing, sized for the new embedder
      3. Scroll through old in batches of N
      4. For each batch: collect payload['text'], call /embeddings,
         upsert into new collection with SAME id + payload
      5. Skip points whose id already exists in the new collection
         (idempotent: safe to resume / re-run)
  - Logs progress every batch.

After migration cutover:
  - Verify counts match: old.count == new.count
  - Either:
    (a) rename: Qdrant doesn't have a native rename, so drop old then
        recreate from new (atomic via aliases — see Qdrant docs)
    (b) point orchestrators at {name}_v2 explicitly
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from typing import Any

import httpx

# Force UTF-8 stdout so Thai-text chunks don't crash print() on Windows.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except Exception:
    pass


async def list_collections(client: httpx.AsyncClient, qdrant: str) -> list[str]:
    r = await client.get(f"{qdrant}/collections")
    r.raise_for_status()
    return [c["name"] for c in r.json()["result"]["collections"]]


async def get_collection_info(client: httpx.AsyncClient, qdrant: str, name: str) -> dict:
    r = await client.get(f"{qdrant}/collections/{name}")
    r.raise_for_status()
    return r.json()["result"]


async def collection_count(client: httpx.AsyncClient, qdrant: str, name: str) -> int:
    r = await client.post(f"{qdrant}/collections/{name}/points/count", json={})
    if r.status_code == 404:
        return -1
    r.raise_for_status()
    return r.json()["result"]["count"]


async def ensure_target_collection(client: httpx.AsyncClient, qdrant: str,
                                    target: str, dim: int, distance: str) -> None:
    # Idempotent: only create if missing
    r = await client.get(f"{qdrant}/collections/{target}")
    if r.status_code == 200:
        return
    body = {"vectors": {"size": dim, "distance": distance}}
    r = await client.put(f"{qdrant}/collections/{target}", json=body)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"failed to create {target}: {r.status_code} {r.text}")


async def existing_ids_in_target(client: httpx.AsyncClient, qdrant: str,
                                 target: str, ids: list) -> set:
    """Return the subset of `ids` already present in the target collection."""
    if not ids:
        return set()
    r = await client.post(
        f"{qdrant}/collections/{target}/points",
        json={"ids": ids, "with_payload": False, "with_vector": False},
    )
    if r.status_code != 200:
        return set()
    return {p["id"] for p in r.json().get("result", [])}


async def embed_batch(client: httpx.AsyncClient, embed_url: str,
                      texts: list[str]) -> list[list[float]]:
    r = await client.post(
        f"{embed_url}/embeddings",
        json={"model": "local-gemma", "input": texts},
    )
    r.raise_for_status()
    data = r.json()["data"]
    # Sort by index to preserve order
    data.sort(key=lambda x: x["index"])
    return [d["embedding"] for d in data]


async def upsert_batch(client: httpx.AsyncClient, qdrant: str, target: str,
                       points: list[dict]) -> None:
    if not points:
        return
    r = await client.put(
        f"{qdrant}/collections/{target}/points?wait=true",
        json={"points": points},
    )
    if r.status_code != 200:
        raise RuntimeError(f"upsert failed: {r.status_code} {r.text[:300]}")


async def detect_embedder_dim(client: httpx.AsyncClient, embed_url: str) -> int:
    vecs = await embed_batch(client, embed_url, ["dimension probe"])
    return len(vecs[0])


async def migrate_collection(client: httpx.AsyncClient, qdrant: str, embed_url: str,
                              source: str, target: str, batch_size: int,
                              new_dim: int) -> tuple[int, int, int]:
    # Read source info, prepare target
    info = await get_collection_info(client, qdrant, source)
    distance = info["config"]["params"]["vectors"]["distance"]
    src_count = info.get("points_count", 0)

    await ensure_target_collection(client, qdrant, target, new_dim, distance)
    print(f"\n=== {source} → {target}  (src points={src_count})", flush=True)

    ok = 0
    skipped = 0
    errors = 0
    next_offset: Any = None
    t0 = time.monotonic()

    while True:
        scroll_body: dict = {
            "limit": batch_size,
            "with_payload": True,
            "with_vector": False,
        }
        if next_offset is not None:
            scroll_body["offset"] = next_offset
        r = await client.post(
            f"{qdrant}/collections/{source}/points/scroll", json=scroll_body
        )
        r.raise_for_status()
        body = r.json()["result"]
        points = body.get("points", []) or []
        next_offset = body.get("next_page_offset")
        if not points:
            break

        ids = [p["id"] for p in points]
        already = await existing_ids_in_target(client, qdrant, target, ids)

        to_embed: list[tuple[Any, dict, str]] = []
        for p in points:
            if p["id"] in already:
                skipped += 1
                continue
            payload = p.get("payload", {}) or {}
            text = payload.get("text") or payload.get("excerpt") or ""
            if not text.strip():
                errors += 1
                continue
            # Cap input length; embeddinggemma-300m max ~2048 tokens
            to_embed.append((p["id"], payload, text[:4000]))

        if not to_embed:
            done = ok + skipped + errors
            elapsed = time.monotonic() - t0
            rate = done / elapsed if elapsed else 0
            print(f"  [{time.strftime('%H:%M:%S')}] {done}/{src_count} "
                  f"ok={ok} skip={skipped} err={errors} · {rate:.1f}/s",
                  flush=True)
            if next_offset is None:
                break
            continue

        try:
            vecs = await embed_batch(client, embed_url, [t for _, _, t in to_embed])
        except Exception as e:  # noqa: BLE001
            print(f"  EMBED ERROR (skipping {len(to_embed)}): {e!s}"[:200], flush=True)
            errors += len(to_embed)
            if next_offset is None:
                break
            continue

        try:
            await upsert_batch(client, qdrant, target, [
                {"id": pid, "vector": vec, "payload": payload}
                for (pid, payload, _), vec in zip(to_embed, vecs)
            ])
            ok += len(to_embed)
        except Exception as e:  # noqa: BLE001
            print(f"  UPSERT ERROR (skipping {len(to_embed)}): {e!s}"[:200], flush=True)
            errors += len(to_embed)

        done = ok + skipped + errors
        if done % (batch_size * 5) == 0 or next_offset is None:
            elapsed = time.monotonic() - t0
            rate = done / elapsed if elapsed else 0
            eta = (src_count - done) / rate if rate else 0
            print(f"  [{time.strftime('%H:%M:%S')}] {done}/{src_count} "
                  f"ok={ok} skip={skipped} err={errors} · {rate:.1f}/s · "
                  f"ETA {eta/60:.1f}min", flush=True)
        if next_offset is None:
            break

    return ok, skipped, errors


async def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--qdrant-url", default="http://localhost:6333")
    p.add_argument("--embed-url", default="http://localhost:8765/v1")
    p.add_argument("--suffix", default="_v2")
    p.add_argument("--batch", type=int, default=64)
    p.add_argument("--collections", default="all",
                   help='Comma-separated list, or "all" to discover.')
    p.add_argument("--skip-empty", action="store_true", default=True,
                   help="Don't bother with collections that have 0 points")
    args = p.parse_args()

    async with httpx.AsyncClient(timeout=120.0) as client:
        new_dim = await detect_embedder_dim(client, args.embed_url)
        print(f"[migrate] embedder dim: {new_dim}", flush=True)

        if args.collections == "all":
            names = await list_collections(client, args.qdrant_url)
            # Don't re-migrate already-v2 collections
            names = [n for n in names if not n.endswith(args.suffix)]
        else:
            names = [n.strip() for n in args.collections.split(",") if n.strip()]

        # Filter empty ones to save time
        if args.skip_empty:
            kept = []
            for n in names:
                c = await collection_count(client, args.qdrant_url, n)
                if c > 0:
                    kept.append((n, c))
                else:
                    print(f"  skip empty: {n} (count={c})", flush=True)
            names = [n for n, _ in kept]

        print(f"[migrate] {len(names)} collections to migrate", flush=True)
        total_ok = total_skip = total_err = 0
        wall_start = time.monotonic()
        for src in names:
            tgt = f"{src}{args.suffix}"
            ok, skip, err = await migrate_collection(
                client, args.qdrant_url, args.embed_url,
                src, tgt, args.batch, new_dim,
            )
            total_ok += ok
            total_skip += skip
            total_err += err
            print(f"  ✓ {src}: ok={ok} skip={skip} err={err}", flush=True)

        print(f"\n[migrate] DONE wall={(time.monotonic()-wall_start)/60:.1f}min "
              f"ok={total_ok} skip={total_skip} err={total_err}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
