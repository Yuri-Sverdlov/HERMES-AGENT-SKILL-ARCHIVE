#!/usr/bin/env bash
# size_test.sh — project the FULL FILE size from short samples, before committing
# to a long encode. Encodes each variant on two segments (20% and 80% of
# duration) and prints the worst-case projection + compression factor.
#
# usage:
#   bash size_test.sh <input> "<label>|<vf>|<crf>|<audio_br>[|<ac>]" [...]
#
# examples:
#   bash size_test.sh "film.mp4" \
#     "360p/15 CRF33 aac32|scale=640:-2,fps=15|33|32k|1" \
#     "540p/20 CRF33 aac96|scale=960:-2,fps=20|33|96k"
#
# fields per variant (pipe-separated):
#   label       free text shown in the table
#   vf          ffmpeg -vf value; use scale=W:-2 to preserve aspect ratio
#   crf         x265 CRF (ignored only if you edit the command to ABR)
#   audio_br    e.g. 32k / 96k
#   ac          optional channel count (1 = mono, 2 = stereo); omitted = source
#
# env:
#   SEG   sample length in seconds (default 60)
#   OUT   scratch output path; must be ffmpeg-visible (Windows-style on MSYS)
#
# NOTE: ffmpeg here is a Windows binary — MSYS paths such as /c/Users/... are NOT
# usable as its arguments. This script converts OUT with cygpath, but the INPUT
# path you pass must already be something ffmpeg can open.
set -u

IN="${1:-}"
[ -n "$IN" ] || { echo "usage: size_test.sh <input> \"label|vf|crf|abr[|ac]\" ..." >&2; exit 2; }
shift
[ "$#" -ge 1 ] || { echo "ERROR: no variants given" >&2; exit 2; }
[ -f "$IN" ] || { echo "ERROR: not found: $IN" >&2; exit 2; }

command -v ffmpeg  >/dev/null || { echo "ERROR: ffmpeg not on PATH"  >&2; exit 2; }
command -v ffprobe >/dev/null || { echo "ERROR: ffprobe not on PATH" >&2; exit 2; }

SEG="${SEG:-60}"
OUT="${OUT:-${TEMP:-${TMP:-C:/Windows/Temp}}/sizetest.mp4}"
case "$OUT" in /*) OUT="$(cygpath -m "$OUT" 2>/dev/null || printf '%s' "$OUT")";; esac

DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$IN" 2>/dev/null)
[ -n "$DUR" ] || { echo "ERROR: cannot probe duration of: $IN" >&2; exit 1; }
SZ0=$(stat -c%s "$IN" 2>/dev/null || echo 0)
[ "$SZ0" -gt 0 ] || { echo "ERROR: cannot stat: $IN" >&2; exit 1; }
if [ "$(awk -v d="$DUR" -v s="$SEG" 'BEGIN{print (d<s+1)?1:0}')" = "1" ]; then
  echo "ERROR: file is shorter than SEG=${SEG}s" >&2; exit 1
fi

OFF1=$(awk -v d="$DUR" 'BEGIN{printf "%.0f", d*0.2}')
OFF2=$(awk -v d="$DUR" 'BEGIN{printf "%.0f", d*0.8}')

printf 'input : %s\n' "$(basename "$IN")"
awk -v sz="$SZ0" -v d="$DUR" -v seg="$SEG" -v o1="$OFF1" -v o2="$OFF2" \
  'BEGIN{printf "        %.1f MB | %.0f s (%.1f min) | samples of %ds at %ss and %ss\n\n", sz/1048576, d, d/60, seg, o1, o2}'

printf '%-30s %10s %10s %12s %8s\n' "variant" "20% sample" "80% sample" "full est" "factor"
printf '%s\n' "-------------------------------------------------------------------------------"

for v in "$@"; do
  IFS='|' read -r label vf crf abr ac <<<"$v"
  [ -n "$label" ] && [ -n "$vf" ] && [ -n "$crf" ] && [ -n "$abr" ] || {
    echo "SKIP bad variant spec: $v" >&2; continue; }

  acargs=()
  [ -n "${ac:-}" ] && acargs=(-ac "$ac")

  worst=0
  s1=""; s2=""
  for pair in "1:$OFF1" "2:$OFF2"; do
    n="${pair%%:*}"; off="${pair#*:}"
    ffmpeg -hide_banner -loglevel error -ss "$off" -t "$SEG" -i "$IN" \
      -vf "$vf" -c:v libx265 -crf "$crf" -preset medium \
      ${acargs[@]+"${acargs[@]}"} -c:a aac -b:a "$abr" -y "$OUT" >/dev/null 2>&1
    if [ ! -f "$OUT" ]; then echo "SKIP encode failed for: $label" >&2; worst=-1; break; fi
    bytes=$(stat -c%s "$OUT")
    if [ "$n" = "1" ]; then s1=$bytes; else s2=$bytes; fi
    [ "$bytes" -gt "$worst" ] && worst=$bytes
    rm -f "$OUT"
  done
  [ "$worst" -gt 0 ] || continue

  awk -v lb="$label" -v a="$s1" -v b="$s2" -v w="$worst" -v sz="$SZ0" -v d="$DUR" -v seg="$SEG" \
    'BEGIN{full=w*d/seg; printf "%-30s %8d KB %8d KB %9.1f MB %7.1fx\n", lb, a/1024, b/1024, full/1048576, sz/full}'
done

echo
echo "factor is size reduction vs the original. Pick settings whose WORST-case factor"
echo "matches the target, then encode the full file and re-verify with ffprobe."
