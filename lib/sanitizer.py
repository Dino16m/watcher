from pathlib import Path
import os
import shutil
import logging
from typing import Optional

from lib import exc
from lib.agent import Agent

logger = logging.getLogger(__name__)


class Sanitizer:

    def __init__(self, agent: Agent, removable_files: Optional[list[str]] = None):
        self._agent = agent
        self._removable_files = removable_files or []

    def _is_removable_file(self, file_name: str):
        for removable in self._removable_files:
            if file_name.endswith(removable):
                return True
        return False

    def clean_empty_dirs(self, target_root: str, file: str):
        path = Path(file)
        parent = path.parent
        logger.info(f"Parent is {str(parent)}")
        while str(parent) != target_root:
            contents = [
                content
                for content in parent.rglob("*")
                if content.is_dir() or not self._is_removable_file(content.name)
            ]
            if len(contents) != 0:
                logger.info(f"{str(parent)} is not empty, skipping")
                break
            removable_contents = [
                content
                for content in Path(target_root).rglob("*")
                if content.is_file() and self._is_removable_file(content.name)
            ]
            for content in removable_contents:
                logger.info(f"Removing file {content.name}")
                content.unlink()
            next_parent = parent.parent
            logger.info(f"removing directory {str(parent)}")
            parent.rmdir()
            parent = next_parent

    def sanitize(self, target_root: str, file: str):
        listing = ", ".join(
            [str(path) for path in Path(target_root).rglob("*") if path.is_dir()]
        )
        try:
            response = self._agent.get_response(target_root, file, f"[{listing}]")
            if response is None:
                raise exc.Retry("Empty response received")
        except exc.ResponseError as e:
            logger.info(
                f"An error occurred when handling file {file} in {target_root}: {str(e)}"
            )
            raise exc.Retry(str(e))

        if response.action == "skip":
            return None

        if not response.destination:
            raise exc.Retry(f"No destination provided for path {file}")
        final_path = (
            Path(response.destination)
            if response.action == "rename"
            else Path(response.destination).joinpath(Path(file).name)
        )
        if final_path.exists():
            logger.info("Final path exists, skipping")
            return
        destination_path = Path(response.destination)
        os.makedirs(
            destination_path if response.action == "move" else destination_path.parent,
            exist_ok=True,
        )
        destination = response.destination
        logger.info(f"Moving file {file} to destination {destination}")
        shutil.move(file, destination)

        self.clean_empty_dirs(target_root, file)

        return destination
