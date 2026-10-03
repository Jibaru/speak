import json
import platform
import sys

from speak.engines.base import Engine, LoadableEngine
from speak.paths import Paths
from speak.settings import Settings
from speak.text.codeswitch import CodeSwitcher

KOKORO_MLX = "kokoro-mlx"
KOKORO_ONNX = "kokoro-onnx"


def is_apple_silicon() -> bool:
    return sys.platform == "darwin" and platform.machine() == "arm64"


def resolve_engine_name(settings: Settings) -> str:
    if settings.engine != "auto":
        return settings.engine
    return KOKORO_MLX if is_apple_silicon() else KOKORO_ONNX


def create_primary(name: str, paths: Paths) -> LoadableEngine:
    switcher = load_switcher(paths)
    if name == KOKORO_MLX:
        from speak.engines.kokoro_mlx import KokoroMlxEngine

        return KokoroMlxEngine(paths, switcher)
    if name == KOKORO_ONNX:
        from speak.engines.kokoro_onnx import KokoroOnnxEngine

        return KokoroOnnxEngine(paths, switcher)
    raise ValueError(f"unknown engine {name!r}")


def create_fallback() -> Engine | None:
    if sys.platform == "darwin":
        from speak.engines.say import SayEngine

        return SayEngine()
    return None


def load_switcher(paths: Paths) -> CodeSwitcher:
    try:
        overrides = json.loads(paths.lexicon_file.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        overrides = {}
    return CodeSwitcher(english=overrides.get("english", ()), native=overrides.get("native", ()))
