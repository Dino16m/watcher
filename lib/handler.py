from pathlib import Path
from queue import Empty, Queue
from typing import Callable
from logging import getLogger

from lib import exc
from lib.sanitizer import Sanitizer
from lib.watcher import FileEvent

logger = getLogger(__name__)


class FileEventHandler:
    def __init__(self, target_root: str, sanitizer: Sanitizer):
        self._queue: Queue[FileEvent] = Queue()
        self._target_root = target_root
        self._ignored_paths: set[str] = set()
        self._sanitizer = sanitizer
        self._attempts: dict[Path, int] = {}

    def handle(self, event: FileEvent) -> None:
        logger.info(f"Received event {event}")
        self._queue.put(event)

    def _retry(self, event: FileEvent):
        attempts = self._attempts.get(event.path, 0)
        attempts += 1
        self._attempts[event.path] = attempts
        self._queue.put(event)

    def process(self, event: FileEvent):
        if event.is_directory or event.event_type != "created":
            return
        if str(event.path.absolute()) in self._ignored_paths:
            self._ignored_paths.remove(str(event.path.absolute()))
            return
        MAX_ATTEMPTS = 3
        if self._attempts.get(event.path, 0) > MAX_ATTEMPTS:
            logger.warning(f"Event exceeded max attempts, skipping: {event}")
            del self._attempts[event.path]
            return

        try:
            path = self._sanitizer.sanitize(self._target_root, str(event.path))
            if path is not None:
                self._ignored_paths.add(path)
        except exc.Retry:
            self._retry(event)
        except Exception as e:
            logger.info(
                f"An unexpected exception occurred when processing event: {event}: {str(e)}",
                exc_info=True,
            )
            self._retry(event)

    def run(self) -> None:
        while True:
            try:
                event = self._queue.get_nowait()
                self.process(event)
            except Empty:
                break
