# AI Model Compass — Roadmap

Zero-config desktop app that matches local LLMs to your hardware, downloads GGUFs from HuggingFace, and integrates with Ollama / LM Studio.

## Completed

- ✅ **v0.7.0** — MoE-aware tok/s estimation (active params for speed, full size for VRAM)
- ✅ **v0.7.0** — Multi-quant tier support per model (Q3_K_M / Q4_K_M / Q5_K_M / Q8_0)
- ✅ **v0.7.0** — Quant upgrade/downgrade hints in ModelCard
- ✅ **v0.7.0** — Added Granite-3.3-8B (IBM, Apache 2.0) and Phi-4 14B (Microsoft, MIT)
- ✅ **v0.7.0** — Version strings unified across all files
- ✅ **v0.8.0** — Added Llama-3.3-70B, DeepSeek-V3 (MoE), Qwen2.5-72B (3 new frontier models)
- ✅ **v0.8.0** — Four-axis scoring in CompareWidget (Quality/Speed/Fit/Context axes)
- ✅ **v0.8.0** — Improved KV cache VRAM formula with framework overhead

## Planned Features

### Core / Model DB
- Expand model DB: DeepSeek-V3, Qwen3-VL-72B, Mistral Large 2
- Add AWQ and GPTQ rows for NVIDIA users (ExLlamaV2 / vLLM downstreams)
- KV cache VRAM calculator (context × layers × heads × bytes)
- Multi-GPU tiled fit (e.g., 2× 3090 → 48 GB effective)

### Integrations
- `vllm` / `tabbyAPI` / `koboldcpp` runtime detection + one-click serve
- `mlx-lm` backend on Apple Silicon (unified memory path)
- llama.cpp `llama-server` direct launch with OpenAI-compatible endpoint
- Docker Model Runner row in Software tab
- `ollama cp` rename helper so downloaded GGUFs register with clean names

### Benchmarking
- Prompt-prefill tok/s vs decode tok/s split (matches llama-bench output)
- Batch-size sweep — charts throughput vs concurrency
- Energy logging — watts per 1M tokens via `nvidia-smi --query-gpu=power.draw`
- Compare mode — pin a baseline run, overlay new results

### UI / UX
- Command palette (`Ctrl+K`) over models, pages, actions
- "Fits on my rig" filter pill — one click across every model view
- Inline GGUF file picker with checksum / sha256 verify against HF
- Download resume after app restart (HF hub supports it; expose the flag)
- Toast when a downloaded model's HF repo publishes a new commit

### Packaging
- PyInstaller `--onefile` build via GitHub Actions (`workflow_dispatch`)
- macOS signed `.app` + Linux AppImage targets
- Portable ZIP with embedded Python so `ai_model_compass.py` runs without system Python

## Competitive Research
- **llmfit** ([AlexsJones/llmfit](https://github.com/AlexsJones/llmfit)) — TUI that scores models on quality/speed/fit; strong download manager + hardware simulator. Steal the simulate-other-hardware feature.
- **LM Studio** — polished GUI for discovery + local OpenAI server. Our edge: smaller footprint and explicit VRAM tier math instead of trial-and-error loads.
- **Jan** — 41k-star open source, hybrid local+cloud chat, MCP integration. Points toward adding a lightweight chat tab so users can try a model without leaving the app.
- **Ollama** — CLI-first. We already pipe to it; add `ollama ps` live view and model delete/unload controls.

## Nice-to-Haves
- HuggingFace search scoped to a user's Liked / Collections pages (requires HF token)
- "Cheapest cloud GPU that runs this" — cross-reference against a curated RunPod/Vast.ai price table
- Prompt-eval harness — run a fixed 50-prompt suite and score quality locally
- Theme import from VS Code color themes (`.json` → QSS)
- Per-model notes attach to downloaded file, export as Obsidian-compatible markdown
- `--headless` CLI mode for scripted downloads on servers

## Open-Source Research (Round 2)

### Related OSS Projects
- **llmfit** — https://github.com/AlexsJones/llmfit — Terminal tool that right-sizes LLMs to RAM/CPU/GPU with interactive TUI; detects NVIDIA/AMD/Intel Arc/Apple/Ascend hardware.
- **llm-checker** — https://github.com/Pavelevich/llm-checker — CLI that scans hardware and scores Ollama-cached models on Quality/Speed/Fit/Context dimensions.
- **whichllm** — https://github.com/Andyyyy64/whichllm — Auto-detects GPU/CPU/RAM, ranks top HuggingFace models that fit, and runs them via isolated uv environments.
- **llm-vram-calculator** — https://github.com/GPUforLLM/llm-vram-calculator — GGUF quantization + GQA context-overhead + KV-cache math for VRAM estimation.
- **selfhostllm** — https://github.com/erans/selfhostllm — Web calculator for GPU memory and max concurrent request estimation.
- **airllm** — https://github.com/lyogavin/airllm — 70B inference on 4GB VRAM via layered offloading; reference for extreme low-VRAM paths.
- **awesome-local-llms** — https://github.com/vince-lam/awesome-local-llms — Metrics-ranked catalog of local LLM inference projects for upstream comparisons.
- **Jan** — https://github.com/janhq/jan — 100% offline ChatGPT-style desktop alt; reference architecture for local-first assistant UX.

### Features to Borrow
- **Dynamic quantization hierarchy** (llmfit) — ✅ partially done: quant tiers + best-fit hints shipped in v0.7.0. Next: auto-walk Q8_0→Q2_K dynamically at runtime.
- **MoE-aware VRAM estimation** (llmfit) — ✅ done in v0.7.0: active-parameter count drives tok/s.
- **Multi-GPU VRAM aggregation** (llmfit) — `nvidia-smi`/`rocm-smi`/`system_profiler` aggregation with graceful fallback to GPU-model-name VRAM tables.
- **Four-axis scoring** (llm-checker) — rank candidates on Quality / Speed / Fit / Context instead of a single "fits/doesn't fit" flag.
- **Scraped-catalog + curated fallback** (llm-checker) — prefer a live-scraped Ollama/HF catalog and fall back to a bundled curated list when offline.
- **One-command run** (whichllm) — spin an isolated uv env, pull the model, and launch an interactive chat session without manual pip/ollama setup.
- **KV cache + activation + framework overhead** (whichllm) — VRAM formula that adds weights + KV cache + activations + ~500MB framework overhead rather than weights-only.
- **System-overhead buffer** (llm-vram-calculator) — reserve VRAM for OS/display out of the budget so recommendations don't crash on first run.
- **Activity-score badges** (awesome-local-llms) — surface last-commit / star-velocity / release cadence next to each suggested model backend so stale ones get visibly demoted.

### Patterns & Architectures Worth Studying
- **TUI + CLI dual frontends** (llmfit) — ship a Textual-style TUI as default and a scriptable CLI mode from the same core library; relevant since AIMC is PyQt6 today and a headless path is missing.
- **Runtime-provider abstraction** (llmfit) — pluggable adapters for Ollama / llama.cpp / MLX / Docker Model Runner / LM Studio behind a common "launch model" interface, so AIMC can grow beyond Ollama without rewriting.
- **Cache + confidence layers** (llm-checker) — local JSON cache with TTL for catalog data plus a confidence score on each recommendation (hardware-detected vs estimated).
- **Layered offloading bookkeeping** (airllm) — track per-layer memory so "doesn't fit in VRAM" becomes "partial offload with N layers to CPU at X tok/s" instead of a hard reject.


Zero-config desktop app that matches local LLMs to your hardware, downloads GGUFs from HuggingFace, and integrates with Ollama / LM Studio.

## Planned Features

### Core / Model DB
- Expand `MODEL_DB` with Llama 4, DeepSeek-V3, Qwen3-VL-72B, Mistral Large 2, Granite 3
- Surface multiple quant tiers per model (Q3_K_S / Q4_K_M / Q5_K_M / Q8_0) instead of Q4_K_M only
- Add AWQ and GPTQ rows for NVIDIA users (ExLlamaV2 / vLLM downstreams)
- Add a MoE-aware speed model — active-parameter count drives tok/s, not total size
- KV cache VRAM calculator (context × layers × heads × bytes)
- Multi-GPU tiled fit (e.g., 2× 3090 → 48 GB effective)

### Integrations
- `vllm` / `tabbyAPI` / `koboldcpp` runtime detection + one-click serve
- `mlx-lm` backend on Apple Silicon (unified memory path)
- llama.cpp `llama-server` direct launch with OpenAI-compatible endpoint
- Docker Model Runner row in Software tab
- `ollama cp` rename helper so downloaded GGUFs register with clean names

### Benchmarking
- Prompt-prefill tok/s vs decode tok/s split (matches llama-bench output)
- Batch-size sweep — charts throughput vs concurrency
- Energy logging — watts per 1M tokens via `nvidia-smi --query-gpu=power.draw`
- Compare mode — pin a baseline run, overlay new results

### UI / UX
- Command palette (`Ctrl+K`) over models, pages, actions
- "Fits on my rig" filter pill — one click across every model view
- Inline GGUF file picker with checksum / sha256 verify against HF
- Download resume after app restart (HF hub supports it; expose the flag)
- Toast when a downloaded model's HF repo publishes a new commit

### Packaging
- PyInstaller `--onefile` build via GitHub Actions (`workflow_dispatch`)
- macOS signed `.app` + Linux AppImage targets
- Portable ZIP with embedded Python so `ai_model_compass.py` runs without system Python

## Competitive Research
- **llmfit** ([AlexsJones/llmfit](https://github.com/AlexsJones/llmfit)) — TUI that scores models on quality/speed/fit; strong download manager + hardware simulator. Steal the simulate-other-hardware feature.
- **LM Studio** — polished GUI for discovery + local OpenAI server. Our edge: smaller footprint and explicit VRAM tier math instead of trial-and-error loads.
- **Jan** — 41k-star open source, hybrid local+cloud chat, MCP integration. Points toward adding a lightweight chat tab so users can try a model without leaving the app.
- **Ollama** — CLI-first. We already pipe to it; add `ollama ps` live view and model delete/unload controls.

## Nice-to-Haves
- HuggingFace search scoped to a user's Liked / Collections pages (requires HF token)
- "Cheapest cloud GPU that runs this" — cross-reference against a curated RunPod/Vast.ai price table
- Prompt-eval harness — run a fixed 50-prompt suite and score quality locally
- Theme import from VS Code color themes (`.json` → QSS)
- Per-model notes attach to downloaded file, export as Obsidian-compatible markdown
- `--headless` CLI mode for scripted downloads on servers

## Open-Source Research (Round 2)

### Related OSS Projects
- **llmfit** — https://github.com/AlexsJones/llmfit — Terminal tool that right-sizes LLMs to RAM/CPU/GPU with interactive TUI; detects NVIDIA/AMD/Intel Arc/Apple/Ascend hardware.
- **llm-checker** — https://github.com/Pavelevich/llm-checker — CLI that scans hardware and scores Ollama-cached models on Quality/Speed/Fit/Context dimensions.
- **whichllm** — https://github.com/Andyyyy64/whichllm — Auto-detects GPU/CPU/RAM, ranks top HuggingFace models that fit, and runs them via isolated uv environments.
- **llm-vram-calculator** — https://github.com/GPUforLLM/llm-vram-calculator — GGUF quantization + GQA context-overhead + KV-cache math for VRAM estimation.
- **selfhostllm** — https://github.com/erans/selfhostllm — Web calculator for GPU memory and max concurrent request estimation.
- **airllm** — https://github.com/lyogavin/airllm — 70B inference on 4GB VRAM via layered offloading; reference for extreme low-VRAM paths.
- **awesome-local-llms** — https://github.com/vince-lam/awesome-local-llms — Metrics-ranked catalog of local LLM inference projects for upstream comparisons.
- **Jan** — https://github.com/janhq/jan — 100% offline ChatGPT-style desktop alt; reference architecture for local-first assistant UX.

### Features to Borrow
- **Dynamic quantization hierarchy** (llmfit) — walk Q8_0 → Q2_K and auto-pick the highest quality quant that fits available memory rather than hardcoding a level per model.
- **MoE-aware VRAM estimation** (llmfit) — detect Mixtral/DeepSeek-V2/V3 families and compute *active*-parameter memory, not total parameters (46.7B → ~12.9B active for Mixtral 8x7B).
- **Multi-GPU VRAM aggregation** (llmfit) — `nvidia-smi`/`rocm-smi`/`system_profiler` aggregation with graceful fallback to GPU-model-name VRAM tables.
- **Four-axis scoring** (llm-checker) — rank candidates on Quality / Speed / Fit / Context instead of a single "fits/doesn't fit" flag.
- **Scraped-catalog + curated fallback** (llm-checker) — prefer a live-scraped Ollama/HF catalog and fall back to a bundled curated list when offline.
- **One-command run** (whichllm) — spin an isolated uv env, pull the model, and launch an interactive chat session without manual pip/ollama setup.
- **KV cache + activation + framework overhead** (whichllm) — VRAM formula that adds weights + KV cache + activations + ~500MB framework overhead rather than weights-only.
- **System-overhead buffer** (llm-vram-calculator) — reserve VRAM for OS/display out of the budget so recommendations don't crash on first run.
- **Activity-score badges** (awesome-local-llms) — surface last-commit / star-velocity / release cadence next to each suggested model backend so stale ones get visibly demoted.

### Patterns & Architectures Worth Studying
- **TUI + CLI dual frontends** (llmfit) — ship a Textual-style TUI as default and a scriptable CLI mode from the same core library; relevant since AIMC is PyQt6 today and a headless path is missing.
- **Runtime-provider abstraction** (llmfit) — pluggable adapters for Ollama / llama.cpp / MLX / Docker Model Runner / LM Studio behind a common "launch model" interface, so AIMC can grow beyond Ollama without rewriting.
- **Cache + confidence layers** (llm-checker) — local JSON cache with TTL for catalog data plus a confidence score on each recommendation (hardware-detected vs estimated).
- **Layered offloading bookkeeping** (airllm) — track per-layer memory so "doesn't fit in VRAM" becomes "partial offload with N layers to CPU at X tok/s" instead of a hard reject.
