# Choosing a TTS engine for a long Russian render

Pick the engine BEFORE the first render: re-voicing 23 h of audio costs ~46 min with Silero and many hours with the
quality models, so a wrong first choice is paid twice.

## Local engines (numbers from ru-speech-bench, Sept 2026, RTX 3090 Ti / 8-vCPU Xeon)
RTF = seconds of synthesis per second of audio (below 1 = faster than real time).
Total render time = audio hours × 3600 × RTF.

| Engine | Runs on | RTF | Russian quality | Weights licence |
|---|---|---|---|---|
| Silero v4_ru `aidar` | CPU/GPU | ~0.03 (274 sections / 23.3 h in 46 min) | even, intelligible, flat | **CC BY-NC** (non-commercial) |
| Silero v5_ru | CPU/GPU | as v4 | newer, richer SSML, `v5_4_ru` handles questions | **CC BY-NC** |
| Piper `denis` / `dmitri` | CPU | 0.20–0.65 | even pace, no clicks; needs number/date normalisation | CC0 (`ruslan` is CC BY-NC-SA; runtime GPL-3.0) |
| Kokoro-82M | CPU/GPU | 0.76 CPU, 0.05 GPU | lively, but Russian goes through a foreign espeak phonemizer → **stress sometimes wrong** | Apache-2.0 |
| XTTS-v2 | GPU | ~0.5, first audio 0.5 s | WER 6.4 %, clones any voice from ~6 s | **CPML non-commercial** |
| F5-TTS Russian fine-tune | GPU | 0.2–0.3 | best local Russian: WER 3.2 % | **CC BY-NC 4.0** |
| Chatterbox Multilingual | GPU only | 22–24 on CPU = unusable | words fine, **digits garbled** | MIT (watermarked output) |
| Qwen3-TTS 1.7B / ESpeech-TTS | GPU | 2.8–3.3 | 4–6 of 5–6 phrases verbatim | Apache-2.0 |
| Fish Audio S1 | cloud/local | — | reported poor Russian stress | non-commercial weights |

Caveats to repeat to the user: the RTF column was measured on a 3090 Ti — the actual ПК1 in this archive's provenance is
an **RTX 3050 8 GB**, i.e. ~4–6× slower; an RTX 4060 would land in between. Verify the card with `nvidia-smi` rather than
trusting a profile — the profile said 4060 while the machine had a 3050.
The benchmark targets phone agents, not audiobooks; over 20+ hours sustained evenness matters more than phrase quality,
and that is where Silero wins. "Non-commercial weights" is irrelevant for audio kept at home, decisive if it ships.

## Cloud engines (prices read from the vendor pricing page)
- **Google Cloud TTS**: Chirp 3 HD $30 / 1M chars with the first 1M chars **free each month**, `ru-RU` supported;
  Neural2 $16 / 1M; Standard $4 / 1M; Studio $160 / 1M. Needs a billing-enabled project and a key.
- **Gemini TTS** (`gemini-2.5-flash-preview-tts`, 3.x): billed per audio minute (~$0.9–1.5 per hour of audio), no free tier.
- **edge-tts**: free, but an unofficial endpoint — Microsoft blocks WSS synthesis for hours with no notice, so it is
  fine for a one-off and wrong as a dependency of a repeatable pipeline.

## Cost recipe (do this instead of guessing)
The characters of the already-prepared RU chunks ARE the bill:
`sum(len(open(f, encoding='utf-8').read()) for f in glob('chunks_ru/**/*'))` — e.g. 1 285 372 chars ≈ 23.3 h of audio.
Chirp 3 HD: that is $0 if spread over two calendar months (1M free each), $8.6 in one go.

## A/B protocol that must precede any re-render
1. Take one section (`001 — раздел 1`) and keep the RU text byte-identical.
2. Render it with the current engine and with the candidate into `ab/<engine>-001.mp3`.
3. Deliver both files to the user and let the ear decide — a 1–2 min sample is what justifies a 23 h re-render.

## Hermes' own TTS surface
`config.yaml` carries `tts.provider` plus per-provider blocks (`edge`, `gemini` → `gemini-2.5-flash-preview-tts`,
`elevenlabs`, `openai`, `xai`, mistral) — the text_to_speech tool can drive them directly when a key exists.
Check for a key by listing variable NAMES only (`grep -oE '^[A-Z0-9_]+'` in `%LOCALAPPDATA%\hermes\.env`, and the
`credential_pool` keys in `auth.json`) — never print or paste values.

## Justifying the work (this user)
State the measured cost (render time, money) and the expected gain before proposing a redo. If the change is cosmetic
(same text, different voice), say that plainly and offer the A/B sample instead of the full job; a redo is only worth
starting after the text itself is final.
