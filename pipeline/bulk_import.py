from __future__ import annotations
import argparse
import asyncio
import sys
from pathlib import Path
from .chunker import CODE_EXTS, MARKDOWN_EXTS, HTML_EXTS, PDF_EXTS, TEXT_EXTS
from .indexer import Indexer


SUPPORTED = CODE_EXTS | MARKDOWN_EXTS | HTML_EXTS | PDF_EXTS | TEXT_EXTS


async def run(root: Path, prefix: str, glob: str, dry_run: bool, only_ext: set[str] | None):
    files = [p for p in root.rglob(glob) if p.is_file() and p.suffix.lower() in (only_ext or SUPPORTED)]
    print(f"found {len(files)} files under {root} (glob={glob})", flush=True)
    if dry_run:
        for p in files[:50]:
            print("DRY", p)
        if len(files) > 50:
            print(f"... and {len(files) - 50} more")
        return
    indexer = Indexer()
    ok, fail = 0, 0
    try:
        for i, p in enumerate(files, 1):
            try:
                rel = p.relative_to(root)
                source = f"{prefix}/{rel.as_posix()}" if prefix else rel.as_posix()
                result = await indexer.index_file(p, source=source)
                ok += 1
                print(f"[{i}/{len(files)}] {source} chunks={result['chunks']} version={result['version']}", flush=True)
            except Exception as e:
                fail += 1
                print(f"[{i}/{len(files)}] FAIL {p}: {e}", file=sys.stderr, flush=True)
    finally:
        await indexer.close()
    print(f"done. ok={ok} fail={fail}")


def main():
    ap = argparse.ArgumentParser(description="Bulk-import files into the RAG index")
    ap.add_argument("path", type=Path, help="Root directory to import")
    ap.add_argument("--prefix", default="", help="Source prefix (e.g. 'claude-doku')")
    ap.add_argument("--glob", default="*", help="Glob pattern (default: *)")
    ap.add_argument("--dry-run", action="store_true", help="List files only, don't index")
    ap.add_argument("--ext", action="append", help="Only these extensions (e.g. --ext .md --ext .pdf)")
    args = ap.parse_args()
    only = set(e.lower() for e in args.ext) if args.ext else None
    asyncio.run(run(args.path.resolve(), args.prefix, args.glob, args.dry_run, only))


if __name__ == "__main__":
    main()
