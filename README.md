# watcher

**AI-powered media file organizer** — automatically sorts downloaded TV episodes
into clean, standardized directory structures using a Large Language Model.

## Overview

`watcher` monitors a download directory for new files and uses a DeepSeek LLM to
parse messy TV episode filenames — stripping website prefixes, tracker tags, and
release group cruft — then moves or renames each file into a `Show Name/SXX/`
hierarchy. It also supports a one-shot `sanitize` mode to batch-process existing
files.

## Features

- **Dual mode**: continuous `watch` via filesystem events, or one-shot `sanitize` for existing files
- **LLM-powered parsing**: handles website prefixes, tracker tags, release groups, multi-episode files, date-based shows, and season packs
- **Retry resilience**: up to 3 attempts per file on transient API or validation errors
- **Duplicate detection**: matches against existing directory names (case-insensitive, separator-normalized) to avoid creating duplicates
- **Self-ignoring**: tracks files it moves so filesystem events triggered by its own operations are skipped
- **Quality tag preservation**: retains resolution, source, codec, audio, and HDR tags when renaming
- **Edge case coverage**: season 00 → `Specials/`, colons replaced for filesystem compatibility, auto-incrementing duplicate filenames
- **Docker support**: ready-to-use image with deterministic dependency locking

## Installation

**Prerequisites:** Python 3.12+ and [`uv`](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/user/watcher.git
cd watcher
uv sync
```

## Configuration

All settings are passed via environment variables:

| Variable     | Required | Default                       | Description                         |
|-------------|----------|-------------------------------|-------------------------------------|
| `API_KEY`    | Yes      | —                             | DeepSeek API key                    |
| `WATCH_DIR`  | Yes      | —                             | Directory to watch or sanitize      |
| `BASE_URL`   | No       | `https://api.deepseek.com`    | API endpoint                        |
| `AGENT_MODEL` | No      | `deepseek-v4-flash`           | Model to use for inference          |
| `LOG_LEVEL`  | No       | `INFO`                        | Python logging level                |

## Usage

**Watch mode** — monitors a directory continuously, processing new files as they appear:

```bash
API_KEY=sk-... WATCH_DIR=./downloads uv run python main.py watch
```

**Sanitize mode** — processes all existing files in a directory once:

```bash
API_KEY=sk-... WATCH_DIR=./downloads uv run python main.py sanitize
```

### Example

| Before                                                                                             | After                                                  |
|----------------------------------------------------------------------------------------------------|--------------------------------------------------------|
| `www.SomeSite.org - Abbott.Elementary.S05E22.1080p.WEB.h264-ETHEL.mkv`                              | `./Abbott Elementary/S05/` (moved, original name)      |
| `[TGx]The.Last.of.Us.S01E03.2160p.x265.mkv`                                                        | `./TV/The Last of Us/S01/The.Last.of.Us.S01E03.2160p.x265.mkv` (renamed) |
| `Breaking.Bad.S03E07E08.720p.BluRay.x264-NTb.mkv`                                                  | `./Breaking Bad/S03/Breaking.Bad.S03E07E08.720p.BluRay.x264.mkv` (renamed) |
| `some_random_file.docx`                                                                            | skipped                                                 |

## Docker

```bash
docker build -t watcher .
docker run -e API_KEY=sk-... -e WATCH_DIR=/data -v ./downloads:/data watcher watch
```

The default entrypoint runs `watch` mode; override `CMD` for batch sanitization:

```bash
docker run -e API_KEY=sk-... -e WATCH_DIR=/data -v ./downloads:/data watcher sanitize
```

## Architecture

The codebase follows a layered design with clear separation of concerns, each
layer owning a single responsibility and communicating through typed interfaces.

### File System Watching (`lib/watcher.py`)

Wraps [Watchdog](https://python-watchdog.readthedocs.io/) behind an adapter
pattern. `DirectoryWatcher` manages the observer lifecycle, converting raw
filesystem callbacks into strongly-typed `FileEvent` dataclasses dispatched to a
pluggable handler. A `watch_directory` context manager provides safe
setup/teardown.

### Event Handling (`lib/handler.py`)

A queue-based worker drains events without blocking the filesystem observer.
Filters out directory events, non-creation events, and self-ignored paths (files
the sanitizer itself moved). Tracks per-file attempt counts and retries on
transient failures, giving up after 3 attempts. Delegates file processing to the
sanitizer.

### AI Agent (`lib/agent.py`)

Contains a detailed system prompt (~160 lines) that instructs the LLM how to
parse filenames, extract show name/season/episode metadata, check against
existing directories, and choose between `move`, `rename`, or `skip` actions.
The prompt encodes rules for edge cases including multi-episode notation,
date-based shows, specials, and filesystem-safe naming. Responses are validated
against a Pydantic `Response` dataclass with a `TypeAdapter`, raising custom
`ResponseError` exceptions on validation failure.

### File Sanitizer (`lib/sanitizer.py`)

Orchestrates the pipeline: builds a directory listing from the target root,
calls the agent for a structured decision, creates target directories as needed,
and performs the filesystem operation via `shutil.move`. Handles both `move`
(preserve filename) and `rename` (apply cleaned name) actions.

### Custom Exceptions (`lib/exc.py`)

A minimal exception hierarchy separates LLM response errors (`ResponseError`)
from transient, retryable conditions (`Retry`), keeping error handling explicit
and type-safe throughout the call chain.

## Tech Stack

| Technology           | Role                                    |
|----------------------|-----------------------------------------|
| Python 3.12+         | Modern type hints, union syntax, `pathlib` |
| [Watchdog][1]        | Cross-platform filesystem event monitoring |
| [OpenAI SDK][2]      | API client (DeepSeek-compatible)        |
| [Pydantic][3]        | Dataclass validation and JSON parsing   |
| [uv][4]              | Package management and deterministic builds |
| Docker               | Containerized deployment                |

[1]: https://python-watchdog.readthedocs.io/
[2]: https://github.com/openai/openai-python
[3]: https://docs.pydantic.dev/
[4]: https://docs.astral.sh/uv/

## Project Structure

```
watcher/
├── main.py                 # CLI entry point (argparse, env config, wiring)
├── lib/
│   ├── __init__.py         # Public API exports
│   ├── watcher.py          # Directory watching layer
│   ├── handler.py          # Event queue, filtering, retry logic
│   ├── agent.py            # LLM prompt and response parsing
│   ├── sanitizer.py        # File move/rename orchestration
│   └── exc.py              # Custom exception hierarchy
├── pyproject.toml          # Project metadata and dependencies
├── uv.lock                 # Locked dependency tree
├── Dockerfile              # Container image definition
└── testdata/               # Manual test fixtures
```
