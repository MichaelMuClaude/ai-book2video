"""Find the Chrome binary used to capture motion frames."""

from __future__ import annotations

import os
import shutil

from ai_book2video.errors import Book2VideoError


def find_chrome() -> str:
    for candidate in (os.environ.get("CHROME_PATH"), "google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        if candidate and shutil.which(candidate):
            return shutil.which(candidate)
    raise Book2VideoError("no Chrome or Chromium found; set CHROME_PATH to the browser binary")


def find_node() -> str:
    found = shutil.which("node")
    if not found:
        raise Book2VideoError("node is needed to capture motion frames (install Node.js 22 or later)")
    return found
