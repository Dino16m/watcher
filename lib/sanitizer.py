from pathlib import Path
import os
import shutil
import logging

from lib import exc
from lib.agent import Agent

logger = logging.getLogger(__name__)


class Sanitizer:
    def __init__(self, agent: Agent):
        self._agent = agent

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

        return destination
