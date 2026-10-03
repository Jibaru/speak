# Phase 0 spike: Kokoro MLX vs ONNX

Machine: Apple M4 Pro, 48 GB. Kokoro-82M, speed 1.15, voices `ef_dora` (es) / `af_heart` (en).

| Engine | First audio (sentence) | RTF | Notes |
|---|---|---|---|
| MLX (`mlx-audio`, bf16) | 128–249 ms | 0.04 | Whole sentence ready at first chunk |
| ONNX (`kokoro-onnx`, CPU) | 399–975 ms | 0.14–0.33 | 325 MB model file |
| macOS `say` (Paulina) | ~260 ms (process incl.) | — | Fallback only |

Cold start (MLX, fresh process): import 0.2 s, load 0.03 s, warm both languages 2.9 s
with `HF_HUB_OFFLINE=1`. Without it, Hugging Face network checks push warm-up to ~20 s.

Decision: MLX. The daemon must run with `HF_HUB_OFFLINE=1` after the first model download,
and must pin `en-core-web-sm` as a dependency (misaki otherwise tries to pip-install it at runtime).
