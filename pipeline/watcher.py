from __future__ import annotations
import asyncio
import logging
import shutil
import time
from pathlib import Path
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from .config import settings
from .indexer import Indexer


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("rag-watcher")


class IndexHandler(FileSystemEventHandler):
    def __init__(self, loop: asyncio.AbstractEventLoop, indexer: Indexer):
        self.loop = loop
        self.indexer = indexer

    def on_created(self, event):
        if event.is_directory:
            return
        asyncio.run_coroutine_threadsafe(self._handle(Path(event.src_path)), self.loop)

    def on_moved(self, event):
        if event.is_directory:
            return
        asyncio.run_coroutine_threadsafe(self._handle(Path(event.dest_path)), self.loop)

    async def _handle(self, path: Path):
        await asyncio.sleep(1.0)
        if not path.exists():
            return
        try:
            inbox = Path(settings.inbox_dir)
            rel = path.relative_to(inbox) if inbox in path.parents or path.parent == inbox else path.name
            source = f"inbox/{rel}"
            log.info("indexing %s as %s", path, source)
            result = await self.indexer.index_file(path, source=source)
            log.info("indexed %s: chunks=%s version=%s deprecated=%s", source, result["chunks"], result["version"], result["deprecated"])
            archive = Path(settings.archive_dir) / Path(rel).with_name(f"{int(time.time())}_{Path(rel).name}")
            archive.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(archive))
        except Exception as e:
            log.exception("index failed for %s: %s", path, e)
            failed = Path(settings.failed_dir) / path.name
            failed.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.move(str(path), str(failed))
            except Exception:
                pass


async def main():
    Path(settings.inbox_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.archive_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.failed_dir).mkdir(parents=True, exist_ok=True)
    indexer = Indexer()
    loop = asyncio.get_running_loop()
    handler = IndexHandler(loop, indexer)
    observer = Observer()
    observer.schedule(handler, settings.inbox_dir, recursive=True)
    observer.start()
    log.info("watching %s", settings.inbox_dir)
    try:
        existing = [p for p in Path(settings.inbox_dir).rglob("*") if p.is_file()]
        for p in existing:
            await handler._handle(p)
        while True:
            await asyncio.sleep(60)
    finally:
        observer.stop()
        observer.join()
        await indexer.close()


if __name__ == "__main__":
    asyncio.run(main())
