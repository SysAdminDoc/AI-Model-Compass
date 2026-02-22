# 🧭 AI Model Compass

![Version](https://img.shields.io/badge/version-0.6.0-blue)
![Python](https://img.shields.io/badge/Python-3.8+-3776AB?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/platform-Windows%20|%20Linux-0078D4)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-active-success)
![Models](https://img.shields.io/badge/models-24%20curated-orange)

> Discover, download, and run local AI models — tailored to your hardware. Zero-config desktop app that auto-detects your GPU, recommends models that fit, and downloads them with one click.

![Screenshot](screenshot.png)

## Quick Start

```bash
git clone https://github.com/SysAdminDoc/AI-Model-Compass.git
cd AI-Model-Compass
python ai_model_compass.py  # Auto-installs all dependencies on first run
```

That's it. No virtual environments, no pip install, no configuration. The app auto-bootstraps PyQt6, psutil, requests, and huggingface_hub on first launch.

### Requirements

- **Python 3.8+** (tested on 3.10–3.14)
- **Internet** for HuggingFace downloads (app itself works offline)
- **GPU** optional — works on CPU-only systems

## What It Does

AI Model Compass solves the "I want to run AI locally, now what?" problem. It scans your hardware, tells you exactly which models fit your GPU, estimates performance, and downloads GGUF files from HuggingFace — all from a single-file desktop app.

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Hardware Scan    │────>│  Model Matching   │────>│  One-Click DL    │
│                  │     │                  │     │                  │
│  GPU / VRAM /    │     │  24 curated      │     │  HuggingFace     │
│  RAM / Bandwidth │     │  models filtered │     │  + Ollama pull   │
│  Auto-detected   │     │  to YOUR specs   │     │  + SW integrate  │
└──────────────────┘     └──────────────────┘     └──────────────────┘
```

## Features

### Core

| Feature | Description |
|---------|-------------|
| Hardware Auto-Detect | GPU, VRAM, CPU, RAM, memory bandwidth — detected at launch |
| Smart Recommendations | Select use cases, get models ranked by fit + performance |
| VRAM Calculator | Drag sliders to see exactly how models fit your GPU |
| Speed Estimation | tok/s predictions based on your GPU's memory bandwidth |
| Model Compatibility | Visual warnings when a model exceeds your VRAM |
| Hardware Refresh | Re-detect GPU without restarting (eGPU, driver updates) |
| System Profile Export | One-click copy of your full hardware specs to clipboard |

### Model Database — 24 Curated Models

| Category | Models | Highlights |
|----------|--------|------------|
| General Purpose | Qwen3-32B, Qwen3-8B, Qwen3-4B, Qwen3-30B-A3B, Qwen3-235B-A22B, DeepSeek-R1-14B, Gemma-3-27B | Thinking modes, MoE, multilingual |
| Coding | Qwen2.5-Coder-32B, Qwen3-Coder-30B-A3B, Devstral-Small-24B | SWE-bench leaders, agentic coding |
| Roleplay | MN-Violet-Lotus-12B, MythoMax-L2-13B, Fimbulvetr-11B-v2, Lumimaid-v0.2-12B, Noromaid-13B | Rich prose, character consistency |
| Uncensored | Dolphin3.0-8B, Nous-Hermes-3-8B, JOSIEFIED-Qwen3-8B | No refusals, abliterated |
| Small / Efficient | Phi-4-Mini (3.8B), SmolLM3-3B | Run on anything |
| Vision | Qwen3-VL-8B | Image + text understanding |
| Agents | Functionary-v3.2-8B | Function calling, JSON output |
| Long Context | Llama-4-Scout, Mistral-Small-24B | 10M+ token context |

Every model is verified against HuggingFace with working download links (Q4_K_M quantization).

### Downloads & Integration

| Feature | Description |
|---------|-------------|
| Download Queue | Queue multiple models — processes sequentially |
| Ollama Pull | One-click `ollama pull` for sharded models (Qwen3-235B, Llama-4-Scout) |
| Ollama Integration | Auto-creates Modelfile and registers downloaded GGUFs |
| LM Studio Integration | Auto-copies GGUFs to LM Studio models directory |
| winget Install | One-click install of Ollama, LM Studio, GPT4All, Jan via winget |
| Download History | Full history with right-click to delete files or open in Explorer |
| VRAM Warnings | Alerts before downloading models that exceed your GPU |

### Benchmarking

| Feature | Description |
|---------|-------------|
| Live Benchmarks | Measure actual tok/s on your hardware via Ollama |
| Bar Chart Visualization | Visual comparison of benchmark results |
| Benchmark History | Track performance across models and dates |
| TTFT Tracking | Time-to-first-token measurement |

### Discovery & Search

| Feature | Description |
|---------|-------------|
| HuggingFace Live Search | Search 800K+ models, filtered to GGUF, sorted by downloads |
| File Browser | Expand any repo to see all GGUF files with quant labels and sizes |
| Direct Download | Download any GGUF from search results with one click |
| Model Comparison | Side-by-side comparison table for up to 3 models |
| Favorites & Notes | Star models, add personal notes, export collection |
| 6 Curated Packs | Beginner Chat, Developer, Roleplay, Freedom, Intelligence, Research |
| Import/Export Packs | Share custom model bundles as JSON |

### UI & Polish

| Feature | Description |
|---------|-------------|
| Sidebar Navigation | 5 grouped sections replacing flat tabs |
| 3 Dark Themes | Obsidian, Catppuccin Mocha, OLED Black |
| Toast Notifications | Slide-in notifications for downloads, installs, benchmarks |
| System Tray | Minimize to tray, background downloads, tray notifications |
| First-Run Wizard | Guided setup with hardware scan + use case picker |
| Educational Content | 6 topics covering AI basics, GGUF, quantization, hardware |
| Searchable Glossary | 30+ AI terms with definitions |
| Update Tracker | Track downloaded models and check for updates |

## Sidebar Navigation

The app organizes 13 pages into 5 logical groups:

```
🏠 Home              ← Dashboard with hardware + software status
🔍 Discover
   ├─ 🗄️ Models      ← Full database with search/filter/sort/compare
   ├─ 🎯 Recommend   ← Use-case-based recommendations
   ├─ 📦 Packs       ← Curated model bundles
   └─ 🔍 HuggingFace ← Live search across 800K+ repos
⬇️ Download
   ├─ ⬇ Downloads    ← Queue, history, software install
   ├─ ★ Favorites    ← Starred models + notes
   └─ 🔄 Updates     ← Track model versions
🧰 Tools
   ├─ 📐 VRAM Calc   ← Interactive VRAM estimation
   ├─ ⚡ Benchmark    ← Live performance testing
   └─ ⚙️ Software    ← 14 tools comparison table
📖 Learn
   ├─ 📖 Topics      ← Educational articles
   └─ 📚 Glossary    ← Searchable term dictionary
```

## How It Works

### Hardware Detection

1. **GPU** — nvidia-smi (NVIDIA) or WMI (AMD/Intel fallback)
2. **VRAM** — Queried directly from GPU driver
3. **CPU** — WMI on Windows, `/proc/cpuinfo` on Linux
4. **RAM** — psutil
5. **Memory Bandwidth** — Lookup table of 45+ GPUs (RTX 20/30/40/50, RX 6000/7000)

### Speed Estimation

```
tok/s ≈ Memory_Bandwidth_GBs / (Model_Size_GB × 1.15)
```

The 1.15x overhead accounts for KV cache and attention. CPU-only systems are capped at DDR bandwidth.

### VRAM Tier System

| Tier | VRAM | Example GPUs | Max GGUF |
|------|------|-------------|----------|
| Ultra | 24 GB+ | RTX 4090, 3090 | ~19.7 GB |
| High | 16 GB | RTX 4070 Ti, 4080 | ~13.1 GB |
| Mid-High | 12 GB | RTX 4070, 3060 12GB | ~9.8 GB |
| Mid | 8 GB | RTX 4060, 3060 | ~6.6 GB |
| Low-Mid | 6 GB | RTX 2060, GTX 1660 | ~4.9 GB |
| Low | 4 GB | GTX 1650 | ~3.3 GB |
| CPU Only | 0 | Integrated / None | ~55% of RAM |

### Software Detection

Auto-detects 5 local AI tools with version numbers:

| Tool | Detection Method | winget ID |
|------|-----------------|-----------|
| Ollama | `ollama --version` + PATH | `Ollama.Ollama` |
| LM Studio | Known install paths | `ElementLabs.LMStudio` |
| KoboldCpp | Known install paths | N/A (URL fallback) |
| GPT4All | Known install paths | `Nomic.GPT4All` |
| Jan | Known install paths | `Jan.Jan` |

## Configuration

All config is stored in `~/.ai_compass/`:

| File | Purpose |
|------|---------|
| `config.json` | Theme, wizard state, preferences |
| `favorites.json` | Starred models and notes |
| `history.json` | Download history (last 50) |
| `benchmarks.json` | Benchmark results (last 30) |
| `update_manifest.json` | Downloaded model tracking |
| `custom_presets.json` | User-imported model packs |
| `crash.log` | Last crash traceback |

Downloaded models save to `~/AI-Models/` by default (configurable).

## Themes

Three built-in dark themes with full QSS styling:

- **Obsidian** — Deep blue-black with blue accents (default)
- **Catppuccin Mocha** — Warm purple-tinted dark with pastel accents
- **OLED Black** — True black for OLED displays

Theme selection persists across sessions.

## FAQ

**Q: Do I need a GPU?**
No. The app works on CPU-only systems. It adjusts model recommendations based on available RAM instead of VRAM.

**Q: Why only Q4_K_M quantization?**
Q4_K_M is the community standard — ~99% quality at 3.3x smaller than FP16. The VRAM Calculator and Learn section explain the tradeoffs. HuggingFace Search lets you download any quantization from any repo.

**Q: Does this replace Ollama / LM Studio?**
No. It complements them. AI Model Compass helps you discover and download models, then integrates directly with Ollama and LM Studio to use them.

**Q: Some models show "Fits" but are slow?**
"Fits" means it loads into VRAM. Speed depends on memory bandwidth. Check the tok/s estimate — under 5 tok/s will feel sluggish. The VRAM Calculator shows this visually.

**Q: How do I run a downloaded model?**
After downloading, click "Register in Ollama" or "Copy to LM Studio". For Ollama: `ollama run model-name`. For LM Studio: the model appears in the sidebar automatically.

## Tech Stack

- **Python 3.8+** — single file, zero external config
- **PyQt6** — native desktop GUI with dark themes
- **huggingface_hub** — model search and downloads
- **psutil** — hardware detection
- **requests** — Ollama API communication
- **2,000 lines** — everything in one file

## Contributing

Issues and PRs welcome. The codebase is a single `ai_model_compass.py` file.

To add a model to the database, add an entry to `MODEL_DB`:

```python
{"n": "Model-Name", "p": "8B", "q": "Q4_K_M", "gb": 5.2, "ctx": "128K",
 "sc": 85, "cat": "General Purpose", "lic": "Apache 2.0",
 "d": "Description of the model.",
 "tags": ["Tag1", "Tag2"],
 "bf": "Best for X",
 "repo": "username/repo-GGUF",
 "file": "model-Q4_K_M.gguf"}
```

## License

MIT
