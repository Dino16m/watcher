import logging
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Literal, Optional

from watchdog.events import (
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    DirCreatedEvent,
    DirDeletedEvent,
    DirModifiedEvent,
    DirMovedEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer
from watchdog.observers.api import BaseObserver

logger = logging.getLogger(__name__)


@dataclass
class FileEvent:
    event_type: Literal["created", "modified", "deleted", "moved"]
    path: Path
    is_directory: bool


class _EventHandler(FileSystemEventHandler):
    def __init__(self, handler: Callable[[FileEvent], None]):
        super().__init__()
        self._handler = handler

    def _dispatch(
        self,
        event_type: Literal["created", "modified", "deleted", "moved"],
        path: str | bytes,
        is_directory: bool,
    ) -> None:
        if isinstance(path, bytes):
            path = path.decode()
        event = FileEvent(
            event_type=event_type, path=Path(path), is_directory=is_directory
        )
        self._handler(event)

    def on_created(self, event: FileCreatedEvent | DirCreatedEvent) -> None:
        self._dispatch("created", event.src_path, event.is_directory)

    def on_modified(self, event: FileModifiedEvent | DirModifiedEvent) -> None:
        self._dispatch("modified", event.src_path, event.is_directory)

    def on_deleted(self, event: FileDeletedEvent | DirDeletedEvent) -> None:
        self._dispatch("deleted", event.src_path, event.is_directory)

    def on_moved(self, event: FileMovedEvent | DirMovedEvent) -> None:
        self._dispatch("moved", event.dest_path, event.is_directory)


class DirectoryWatcher:
    def __init__(
        self,
        directory: str | Path,
        handler: Callable[[FileEvent], None],
        *,
        recursive: bool = True,
        patterns: Optional[list[str]] = None,
        ignore_patterns: Optional[list[str]] = None,
    ):
        self._directory = str(directory)
        self._handler = handler
        self._recursive = recursive
        self._patterns = patterns
        self._ignore_patterns = ignore_patterns
        self._observer: Optional[BaseObserver] = None
        self._running = False

    def start(self) -> None:
        if self._running:
            return

        event_handler = _EventHandler(self._handler)
        self._observer = Observer()
        self._observer.schedule(
            event_handler,
            self._directory,
            recursive=self._recursive,
        )
        self._observer.start()
        self._running = True
        logger.info("Started watching %s", self._directory)

    def stop(self) -> None:
        if not self._running or self._observer is None:
            return

        self._observer.stop()
        self._observer.join()
        self._observer = None
        self._running = False
        logger.info("Stopped watching %s", self._directory)


@contextmanager
def watch_directory(
    directory: str | Path,
    handler: Callable[[FileEvent], None],
    *,
    recursive: bool = True,
    patterns: Optional[list[str]] = None,
    ignore_patterns: Optional[list[str]] = None,
):
    watcher = DirectoryWatcher(
        directory,
        handler,
        recursive=recursive,
        patterns=patterns,
        ignore_patterns=ignore_patterns,
    )
    watcher.start()
    try:
        yield watcher
    finally:
        watcher.stop()
