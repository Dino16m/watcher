import argparse
import logging
import os
import time
from pathlib import Path

from openai import OpenAI

from lib import exc
from lib.agent import Agent
from lib.handler import FileEventHandler
from lib.sanitizer import Sanitizer
from lib.watcher import watch_directory

logger = logging.getLogger(__name__)
logging.basicConfig(
    format="[%(asctime)s] [%(levelname)s]: %(message)s",
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
)


def watch(watch_dir: str, sanitizer: Sanitizer):
    handler = FileEventHandler(watch_dir, sanitizer)

    with watch_directory(watch_dir, handler.handle):
        while True:
            handler.run()
            time.sleep(10)


def sanitize(watch_dir: str, sanitizer: Sanitizer):
    files = list(Path(watch_dir).rglob("*"))
    files = [file for file in files if file.is_file()]
    attempts: dict[Path, int] = {}
    max_attempts = 3
    moved = 0
    skipped = 0
    errors = 0

    while len(files):
        file = files.pop(0)
        attempt = attempts.get(file, 0)
        if attempt > max_attempts:
            errors += 1
            logger.warning(f"Exhausted max attempts for file: {file}, skipping")
            del attempts[file]
            continue
        try:
            result = sanitizer.sanitize(watch_dir, str(file))
            if result:
                logger.info("Sanitized %s -> %s", file, result)
                moved += 1
            else:
                logger.info("Skipped %s", file)
                skipped += 1
        except exc.Retry:
            logger.warning("Queuing %s for retry", file)
            files.append(file)
            attempt = attempts.get(file, 0)
            attempt += 1
            attempts[file] = attempt
        except Exception as e:
            logger.error(
                f"An unexpected error occurred: {str(e)}, queuing for retry: {file}"
            )
            files.append(file)
            attempt = attempts.get(file, 0)
            attempt += 1
            attempts[file] = attempt

    logger.info(
        f"Processed {moved + skipped + errors} files; moved {moved}; skipped {skipped}; errors {errors}"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode",
        nargs="?",
        choices=["watch", "sanitize"],
        default="watch",
    )
    args = parser.parse_args()

    api_key = os.environ["API_KEY"]
    watch_dir = os.environ["WATCH_DIR"]
    base_url = os.environ.get("BASE_URL", "https://api.deepseek.com")
    agent_model = os.environ.get("AGENT_MODEL", "deepseek-v4-flash")

    client = OpenAI(
        base_url=base_url,
        api_key=api_key,
    )

    sanitizer_instance = Sanitizer(Agent(client, agent_model))

    if args.mode == "watch":
        watch(watch_dir, sanitizer_instance)
    elif args.mode == "sanitize":
        sanitize(watch_dir, sanitizer_instance)


if __name__ == "__main__":
    main()
