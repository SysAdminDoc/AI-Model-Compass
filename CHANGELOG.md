# Changelog

All notable changes to AI-Model-Compass will be documented in this file.

## [v0.7.0] - 2025-07-10

- Added: MoE-aware token/s estimation — active params used for speed (VRAM check still uses full size)
- Added: Multi-quant tier support in models.json (Q3_K_M, Q4_K_M, Q5_K_M, Q8_0 per model)
- Added: Quant upgrade/downgrade hints in ModelCard — shows best available quant for your hardware
- Added: MoE label on speed display for mixture-of-experts models
- Added: Granite-3.3-8B (IBM, Apache 2.0) — enterprise-grade 8B, strong coding + general tasks
- Added: Phi-4 14B (Microsoft, MIT) — exceptional reasoning and STEM, 16K context
- Fixed: Version strings aligned across all files (README badge, CLAUDE.md, CHANGELOG)

## [v0.6.0] - 2025-06-01

- Changed: Refactor MODEL_DB to external models.json with auto-update
- Changed: Update README.md
- Added: Add files via upload
