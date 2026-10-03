import logging
import urllib.request
from pathlib import Path

log = logging.getLogger(__name__)


def ensure_file(url: str, destination: Path) -> Path:
    if destination.exists():
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    log.info("downloading %s", url)
    urllib.request.urlretrieve(url, partial)
    partial.replace(destination)
    return destination
