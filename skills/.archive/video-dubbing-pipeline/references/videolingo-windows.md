# VideoLingo on Windows — config, layout, measured numbers

Session detail behind the `video-dubbing-pipeline` skill. Machine: [ПК1: RTX 3050 8 GB],
Windows, project `G:\_MY-PROGRAMMING_3\VIDEO-TRANSLATE-BATCH`, VideoLingo 3.0.3 at
upstream commit `814f84e` ("Replace dead Yunwu default with OpenRouter DeepSeek V4 Flash").

## Install (already done, kept for rebuilds)

```bash
git clone https://github.com/Huanshere/VideoLingo.git
cd VideoLingo && py setup_env.py 2>&1 | tee ../logs/setup.log
```

`setup_env.py` finds `uv`, creates a **Python 3.10** `.venv`, then runs `installer.py --yes`.
The installer auto-detects CUDA from `nvidia-smi` and picks the torch index — driver 591.86
→ `https://download.pytorch.org/whl/cu129`, torch 2.8.0+cu129 (3.57 GB wheel).
Result check it prints itself:

```
streamlit 1.49.1 / torch 2.8.0+cu129 / torchaudio 2.8.0+cu129 / spacy 3.8.16 / whisperx 3.8.6 / demucs 4.1.0a3
```

Nothing extra had to be installed. No CUDA Toolkit. Total ~14 min, ~8.5 GB on G: plus
~6.5 GB in the global HF cache on C: (`C:\Users\<user>\.cache\huggingface\hub`).

## config.yaml fields that matter

| Key | Value for EN→RU | Note |
|---|---|---|
| `api.key` | `sk-or-v1-...` | OpenRouter, NOT a DeepSeek key |
| `api.base_url` | `https://openrouter.ai/api/v1` | change to `https://api.deepseek.com` only if the key is DeepSeek's |
| `api.model` | `deepseek/deepseek-v4-flash` | repo default is fine |
| `target_language` | `Russian` | natural language, written straight into the prompt |
| `whisper.model` | `large-v3` | fits 8 GB next to ~2 GB desktop usage — barely |
| `whisper.language` | `en` | |
| `whisper.runtime` | `local` | `cloud` needs a 302.ai key |
| `tts_method` | `edge_tts` | repo default `azure_tts` needs a paid 302.ai key |
| `edge_tts.voice` | `ru-RU-DmitryNeural` | single voice for the whole file |
| `demucs` | `false` | vocal separation; off for single-speaker material |
| `pause_before_translate` | `false` | `true` halts for manual terminology edits |
| `burn_subtitles` | `true` | |

`display_language: zh-CN` only affects the Streamlit UI language — leave it.
The config ships with `key: 'YOUR_API_KEY'`; if it is still the placeholder, STOP and ask —
and check the file's mtime before believing the owner saved it (a claimed edit with an
unchanged mtime means the write never landed).

## Stage mapping used in the report

`process_video` runs eleven steps; the acceptance table names four buckets:

| Bucket | Steps |
|---|---|
| 1 Recognition | Processing input file + Transcribing with Whisper |
| 2 Translation | Splitting sentences + Summarizing and translating + Processing and aligning subtitles |
| 3 Synthesis | Generating audio tasks + Extracting reference audio + Generating audio + Merging full audio |
| 4 Assembly | Merging subtitles to video + Merging dubbing to video |

The subtitle mux belongs to no bucket as written — assign it explicitly and say so.

## Measured run (9-min English dialogue -> Russian, RTX 3050 8 GB)

Source `3364.mp4`: 540.143 s, 854x480 h264, aac 44100 stereo, 59.8 MB. Dialogue
(male + female), not a monologue.

| Quantity | Value |
|---|---|
| Total wall clock | 650.12 s |
| Stage 1 recognition | 104.78 s (WhisperX alone 104.63) |
| Stage 2 translation | 184.09 s (split 19.19 incl. spaCy download, translate 164.62, align 0.28) |
| Stage 3 synthesis | 185.00 s (refer audio 87.04, gen audio 82.96, merge 13.49) |
| Stage 4 assembly | 175.92 s (subtitle mux 66.28, dub mux 109.64) |
| Whisper | large-v3, cuda, float16, batch size 2, pyannote VAD |
| Peak VRAM | 7134 MiB of 8192 (nvidia-smi); baseline 2212 MiB |
| GPU util stage 1 | max 100 %, avg 38.8 %, 100 % of samples > 0 |
| Segments | 94 source / 94 translated, 2311 EN chars, 1979 RU chars |
| Final video | 540.160 s (drift 0.004 %); audio stream 540.029 s |
| TTS track | 526.864 s — 2.46 % shorter than the video, stretched at mux |
| API cost | not logged |

Rough shape for planning: ~1.2x realtime end to end on this card, and the ASR stage is the
only one that really needs the GPU — every stage still showed util > 0 because ffmpeg keeps
the encoder busy.

## Output layout (surprise: `output/` ends up EMPTY)

`process_video` ends with `cleanup(SAVE_DIR)`, so everything lands in
`batch/output/<input-stem>/`, and the working `output/` directory is left empty:

```
batch/output/3364/
  output_dub.mp4        49.2 MB  540.160 s   final, dubbed
  output_sub.mp4        51.7 MB  540.160 s   subtitled variant
  dub.mp3                4.2 MB  526.864 s   generated target-language track
  normalized_dub.wav    16.9 MB  526.864 s
  src.srt / trans.srt / src_trans.srt / trans_src.srt / dub.srt
  gpt_log/error.json                            failed LLM batch, see below
```

## Silent partial failures worth knowing about

- **LLM JSON validation.** Log line:
  `GPT request failed: API response error: Missing required key(s): 9, 10,` plus
  `Moved: output/gpt_log\error.json -> batch/output\<stem>\gpt_log\error.json` and
  `retry: 1/5`. The retry succeeded, the run reported `ok=True`, and the affected segment
  pair was fine. But `ok=True` is NOT proof: if all 5 retries fail the step raises. Always
  machine-check the SRT (empty blocks / blocks without target-script characters) and report
  the retry count from the log.
- **spaCy model download.** `core/spacy_utils/load_nlp_model.py` catches the first
  `spacy.load()` failure and calls `spacy.cli.download(...)`. A fresh venv has no
  `en_core_web_md`, so the first split step silently spends time on a download.
- **WhisperX cache.** `model_dir: './_model_cache'` is empty after install; the log says
  `Project model cache is incomplete; falling back to the global HuggingFace cache.`
- **Harmless noise:** `Model was trained with torch 1.10.0+cu102, yours is 2.0.0+cu118`
  (WhisperX) and `Lightning automatically upgraded your loaded checkpoint from v1.5.4 to
  v2.6.1`. Do not "fix" these.

## cuBLAS on this stack

`ctranslate2\` contained `cudnn64_9.dll` but no `cublas64_12.dll` — the exact layout that
hangs in the whisper-local app (see `mlops/stt-whisper-gpu-windows`) — yet WhisperX ran on
CUDA first try, in both the isolated probe and the full pipeline. The working hypothesis is
import order: torch is imported before CTranslate2 loads its model, and torch registers
`torch\lib` (which ships `cublas64_12.dll` / `cublasLt64_12.dll`) in the Windows DLL search
path. Consequence: a standalone probe passing is not proof that every entry point is safe,
but for VideoLingo the battle path itself now has evidence.
