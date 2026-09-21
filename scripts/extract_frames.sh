#!/usr/bin/env bash
# extract_frames.sh <视频> [输出目录] [每秒帧数] [切镜阈值]
# 产出：first.png（第一帧）、last.png（真正的最后一个可解码帧，时间写在 last.txt）、sec_%03d.png（每秒一帧）、
#       cut_%03d.png（切镜检测，阈值默认 0.3）、cuts.txt（切点时间或失败原因）、tile.png（拼图）、run.txt（本次运行记录）、
#       .aigc-frames.manifest（本脚本生成过的文件清单，重复运行只清理清单里的文件）
# 退出码：0 全部成功；2 缺依赖、输入错误或首尾帧失败；3 部分成功（切镜检测或拼图失败，已生成的图保留，run.txt 写明）
# 证据边界：抽帧只能定位切点与状态；正常速度的节奏、接触瞬间、声音关系要连续播放和听审，拼图证明不了。
set -uo pipefail
VIDEO="${1:?用法: extract_frames.sh <视频> [输出目录] [每秒帧数] [切镜阈值]}"
OUT="${2:-${VIDEO%.*}_frames}"
FPS="${3:-1}"
SCENE="${4:-0.3}"
for tool in ffmpeg ffprobe; do
  command -v "${tool}" >/dev/null || { echo "需要 ${tool}（brew install ffmpeg）" >&2; exit 2; }
done
[ -f "${VIDEO}" ] || { echo "找不到视频：${VIDEO}" >&2; exit 2; }
mkdir -p "${OUT}" || exit 2
TMP_RUN=$(mktemp -d "${TMPDIR:-/tmp}/aigc-frames.XXXXXX") || exit 2
trap 'rm -rf "${TMP_RUN}"' EXIT
OWNED_NAME_RE='^(first\.png|last\.png|last\.txt|tile\.png|cuts\.txt|run\.txt|(sec|cut)_[0-9]+\.png)$'
MANIFEST="${OUT}/.aigc-frames.manifest"
# 只清理本脚本上一次记录在清单里的文件；目录里有同名但不是本脚本生成的文件时拒绝运行，避免混进旧图或误删
if [ -f "${MANIFEST}" ]; then
  while IFS= read -r f; do
    [[ "${f}" =~ ${OWNED_NAME_RE} ]] || { echo "输出清单含非法文件名，停止清理" >&2; exit 2; }
  done < "${MANIFEST}"
  while IFS= read -r f; do rm -f "${OUT}/${f}"; done < "${MANIFEST}"
  rm -f "${MANIFEST}"
fi
STRANGERS=$(cd "${OUT}" && ls first.png last.png last.txt tile.png cuts.txt run.txt sec_*.png cut_*.png 2>/dev/null | tr '\n' ' ')
if [ -n "${STRANGERS}" ]; then
  echo "输出目录里有不是本脚本生成的同名文件：${STRANGERS}；换一个输出目录或自行移走" >&2; exit 2
fi
: > "${MANIFEST}"
own() { echo "$1" >> "${MANIFEST}"; }
STATUS=0
{
  echo "运行时间: $(date '+%Y-%m-%d %H:%M:%S')"; echo "视频: ${VIDEO}"; echo "ffmpeg: $(ffmpeg -version 2>/dev/null | head -1)"
} > "${OUT}/run.txt"; own run.txt
DUR=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "${VIDEO}" 2>/dev/null || echo 0)
echo "时长(秒): ${DUR}" | tee -a "${OUT}/run.txt"
# 首帧
if ffmpeg -v error -y -i "${VIDEO}" -frames:v 1 "${OUT}/first.png"; then own first.png; else echo "首帧失败" | tee -a "${OUT}/run.txt"; STATUS=2; fi
# 真正的最后一帧：从结尾前 1 秒起逐帧覆盖同一文件，留下的就是最后一个可解码帧；-copyts 让 showinfo 记录绝对时间
ffmpeg -v info -nostats -y -sseof -1 -copyts -i "${VIDEO}" -vf showinfo -update 1 "${OUT}/last.png" 2>"${TMP_RUN}/last.log"
LAST_T=$(grep -o "pts_time:[0-9.]*" "${TMP_RUN}/last.log" | tail -1 | sed 's/pts_time://')
rm -f "${TMP_RUN}/last.log"
if [ -f "${OUT}/last.png" ] && [ -n "${LAST_T:-}" ]; then
  own last.png; own last.txt
  echo "尾帧时间(秒): ${LAST_T}（最后一个可解码帧）" | tee "${OUT}/last.txt" | tee -a "${OUT}/run.txt"
else
  echo "尾帧失败（没有得到最后一帧或它的时间）" | tee -a "${OUT}/run.txt"; STATUS=2
fi
# 每秒一帧
if ffmpeg -v error -y -i "${VIDEO}" -vf "fps=${FPS}" "${OUT}/sec_%03d.png"; then
  for f in "${OUT}"/sec_*.png; do [ -f "${f}" ] && own "$(basename "${f}")"; done
else
  echo "抽样帧失败" | tee -a "${OUT}/run.txt"; STATUS=2
fi
# 切镜检测：按当前 ffmpeg 支持的帧同步选项；失败时明确报告，不吞掉
if [ "$(ffmpeg -hide_banner -h full 2>&1 | grep -c fps_mode)" -gt 0 ]; then SYNC=(-fps_mode vfr); else SYNC=(-vsync vfr); fi
own cuts.txt
if ffmpeg -v info -nostats -y -i "${VIDEO}" -vf "select='gt(scene,${SCENE})',showinfo" "${SYNC[@]}" "${OUT}/cut_%03d.png" 2>"${TMP_RUN}/cuts.log"; then
  grep -o "pts_time:[0-9.]*" "${TMP_RUN}/cuts.log" | sed 's/pts_time:/切镜时间点(秒): /' > "${OUT}/cuts.txt"
  for f in "${OUT}"/cut_*.png; do [ -f "${f}" ] && own "$(basename "${f}")"; done
  NCUT=$(ls "${OUT}"/cut_*.png 2>/dev/null | wc -l | tr -d ' ')
  echo "切镜检测: 成功，检出 ${NCUT} 处（阈值 ${SCENE}；闪光可能被误判为切点，核对对应帧）" | tee -a "${OUT}/run.txt"
  cat "${OUT}/cuts.txt"
else
  echo "切镜检测: 失败（原因见下），首尾帧与抽样帧仍可用" | tee -a "${OUT}/run.txt"
  { echo "切镜检测失败，未生成 cut_*.png"; tail -3 "${TMP_RUN}/cuts.log"; } | tee "${OUT}/cuts.txt"
  [ "${STATUS}" -eq 0 ] && STATUS=3
fi
rm -f "${TMP_RUN}/cuts.log"
# 拼图
N=$(ls "${OUT}"/sec_*.png 2>/dev/null | wc -l | tr -d ' ')
if [ "${N}" -gt 0 ]; then
  COLS=6; ROWS=$(( (N + COLS - 1) / COLS ))
  if ffmpeg -v error -y -i "${OUT}/sec_%03d.png" -vf "scale=320:-1,tile=${COLS}x${ROWS}" "${OUT}/tile.png"; then own tile.png; else
    echo "拼图失败" | tee -a "${OUT}/run.txt"; [ "${STATUS}" -eq 0 ] && STATUS=3; fi
fi
case "${STATUS}" in 0) echo "结果: 全部成功" ;; 3) echo "结果: 部分成功（见上）" ;; *) echo "结果: 失败" ;; esac | tee -a "${OUT}/run.txt"
echo "输出目录: ${OUT}"; ls -1 "${OUT}"
exit "${STATUS}"
