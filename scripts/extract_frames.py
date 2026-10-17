#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_frames.py <视频> [输出目录] [每秒帧数] [切镜阈值]   （跨平台版，macOS 与 Windows 通用；extract_frames.sh 只是转调本脚本）
产出：first.png（第一帧）、last.png（真正的最后一个可解码帧，时间写在 last.txt）、sec_%03d.png（每秒一帧）、
      cut_%03d.png（切镜检测，阈值默认 0.3）、cuts.txt（切点时间或失败原因）、tile.png（拼图）、run.txt（本次运行记录）、
      motion.txt / motion.json（v47：每半秒运动量、近乎静止段、定住与重演候选；缺 numpy 时跳过，不影响退出码），
      .aigc-frames.manifest（本脚本生成过的文件清单，重复运行只清理清单里的文件）
退出码：0 全部成功；2 缺依赖、输入错误或首尾帧失败；3 部分成功（切镜检测或拼图失败，已生成的图保留，run.txt 写明）
证据边界：抽帧只能定位切点与状态；正常速度的节奏、接触瞬间、声音关系要连续播放和听审，拼图证明不了。
运动量是看片的尺子，不是验收线：160×90 灰度相邻帧差的均值（0–255），按半秒分段，段均值 < 1.5 记近乎静止；相隔 ≥ 0.75 秒、
  差值 < 5 的两帧连成段，中间没动过记「定住」，动过记「重演候选」并给最像的一对当可剪点（阈值按一组 6 条 7 秒样片校的，别的画风
  不一定适用）。它量的是整幅画面有多少像素变了，大景别里又小又快的主体读数也低，读数低先看帧（diagnose 第 2 节）。
ffmpeg / ffprobe 查找顺序：PATH → 环境变量 FFMPEG_DIR → 常见安装位置（/opt/homebrew/bin、/usr/local/bin；Windows 的 C:\\ffmpeg\\bin 等）。
"""
import datetime, json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

USAGE = "用法: extract_frames.py <视频> [输出目录] [每秒帧数] [切镜阈值]"
OWNED_NAME_RE = re.compile(r"^(first\.png|last\.png|last\.txt|tile\.png|cuts\.txt|run\.txt|motion\.txt|motion\.json|(sec|cut)_[0-9]+\.png)$")
FIXED_NAMES = ("first.png", "last.png", "last.txt", "tile.png", "cuts.txt", "run.txt", "motion.txt", "motion.json")
MOTION_SIZE, MOTION_STILL, MOTION_GAP, MOTION_SAME = (160, 90), 1.5, 0.75, 5.0   # 运动量参数，见文件头
PTS = re.compile(r"pts_time:([0-9.]*)")


def find_tool(name):
    exe = name + (".exe" if os.name == "nt" else "")
    p = shutil.which(name)
    if p:
        return p
    dirs = []
    if os.environ.get("FFMPEG_DIR"):
        dirs.append(os.environ["FFMPEG_DIR"])
    if os.name == "nt":
        dirs += [r"C:\ffmpeg\bin", r"C:\Program Files\ffmpeg\bin"]
        dirs += [str(d / "bin") for d in Path("C:/").glob("ffmpeg*")]
    else:
        dirs += ["/opt/homebrew/bin", "/usr/local/bin"]
    for d in dirs:
        c = os.path.join(d, exe)
        if os.path.isfile(c):
            return c
    return None


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def sec_files(out):
    return sorted(p for p in out.glob("sec_*.png") if p.is_file())


def motion_analyze(frames, fps, seg, still=MOTION_STILL, gap_s=MOTION_GAP, same=MOTION_SAME):
    """frames：(n, h, w) uint8 灰度帧。返回 (相邻帧差, 半秒段, 定住段, 重演候选)，口径见文件头。"""
    import numpy as np
    f = frames.astype(np.int16)
    n = len(f)
    diffs = np.abs(f[1:] - f[:-1]).mean(axis=(1, 2))
    segs = []
    for k in range(0, len(diffs), seg):
        d = diffs[k:k + seg]
        m = float(d.mean())
        segs.append({"t0": k / fps, "t1": (k + len(d)) / fps, "motion": m, "still": m < still, "partial": len(d) < seg})
    # 相似帧对：每一帧往后找相隔 ≥ gap 的最像的一帧；相邻起点、偏移差不超过 2 帧的连成一段
    gap = max(1, int(round(gap_s * fps)))
    runs = []
    for i in range(0, n - gap):
        cand = np.abs(f[i + gap:] - f[i]).mean(axis=(1, 2))
        j = int(cand.argmin())
        if cand[j] >= same:
            continue
        j, d = i + gap + j, float(cand[j])
        if runs and i - runs[-1]["i1"] <= 1 and abs((j - i) - runs[-1]["off"]) <= 2:
            runs[-1]["i1"], runs[-1]["j1"] = i, j
            runs[-1]["pairs"].append((i, j, d))
        else:
            runs.append({"i0": i, "i1": i, "j0": j, "j1": j, "off": j - i, "pairs": [(i, j, d)]})
    holds, k = [], 0
    while k < len(segs):
        m = k
        while segs[k]["still"] and m + 1 < len(segs) and segs[m + 1]["still"]:
            m += 1
        if m > k:
            holds.append({"t0": segs[k]["t0"], "t1": segs[m]["t1"], "segs": m - k + 1})
        k = m + 1
    repeats = []
    for r in runs:
        between = diffs[r["i0"]:r["j1"]]
        if len(r["pairs"]) < 2 or (len(between) and between.mean() < still * 1.5):   # 孤立一对不报；中间没动过归「定住」
            continue
        i, j, d = min(r["pairs"], key=lambda p: p[2])
        x = {"a": [r["i0"] / fps, r["i1"] / fps], "b": [r["j0"] / fps, r["j1"] / fps], "cut": [i / fps, j / fps], "min_diff": d}
        # 第二遍常比第一遍快或慢，最像的那帧会把一段拆碎：a 段连着、b 段挨着就并成一条
        if repeats and x["a"][0] <= repeats[-1]["a"][1] + 2.5 / fps and abs(x["b"][0] - repeats[-1]["b"][1]) <= 0.3:
            m = repeats[-1]
            m["a"][1] = max(m["a"][1], x["a"][1])
            m["b"] = [min(m["b"][0], x["b"][0]), max(m["b"][1], x["b"][1])]
            if d < m["min_diff"]:
                m["min_diff"], m["cut"] = d, x["cut"]
        else:
            repeats.append(x)
    return diffs, segs, holds, repeats


def motion_report(ffmpeg, ffprobe, video, out, own, log):
    """写 motion.txt / motion.json；缺 numpy 或解码失败只记一行，不改退出码。"""
    try:
        import numpy as np
    except ImportError:
        log("运动量: 跳过（需要 numpy：py -3 -m pip install numpy，macOS 用 python3 -m pip install numpy）")
        return
    p = run([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=avg_frame_rate,r_frame_rate",
             "-of", "default=nw=1:nk=1", video])
    fps = 0.0
    for r in p.stdout.split():
        a, _, b = r.partition("/")
        try:
            fps = fps or float(a) / float(b or 1)
        except (ValueError, ZeroDivisionError):
            pass
    w, h = MOTION_SIZE
    q = subprocess.run([ffmpeg, "-v", "error", "-i", video, "-vf", f"scale={w}:{h},format=gray",
                        "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1"], capture_output=True)
    n = len(q.stdout) // (w * h)
    if q.returncode != 0 or n < 2 or fps <= 0:
        log("运动量: 失败（解码或帧率读取失败），其他产出不受影响")
        return
    frames = np.frombuffer(q.stdout[: n * w * h], dtype=np.uint8).reshape(n, h, w)
    seg = max(1, int(round(fps / 2)))
    diffs, segs, holds, repeats = motion_analyze(frames, fps, seg)
    lines = [f"运动量（{w}×{h} 灰度相邻帧差均值，{fps:.2f} fps，{seg} 帧一段≈半秒；看片的尺子，不是验收线）",
             "起止秒 | 运动量 | 曲线（每个 # 是 0.5）"]
    for sg in segs:
        tag = "  ← 近乎静止" if sg["still"] else ""
        lines.append(f"{sg['t0']:.2f}–{sg['t1']:.2f} | {sg['motion']:.1f} | {'#' * min(40, int(round(sg['motion'] / 0.5)))}{tag}"
                     + ("（不足一段）" if sg["partial"] else ""))
    n_still = sum(1 for sg in segs if sg["still"])
    lines.append(f"均值 {float(diffs.mean()):.1f}，近乎静止的段 {n_still}/{len(segs)}（段均值 < {MOTION_STILL:g}）")
    lines += [f"定住：{hd['t0']:.2f}–{hd['t1']:.2f} 秒连续 {hd['segs']} 段近乎静止" for hd in holds]
    lines += [f"重演候选：{r['a'][0]:.2f}–{r['a'][1]:.2f} 秒与 {r['b'][0]:.2f}–{r['b'][1]:.2f} 秒相似（最小差 {r['min_diff']:.1f}）；"
              f"可剪点候选 {r['cut'][0]:.2f} → {r['cut'][1]:.2f} 秒，先看这两帧再定" for r in repeats]
    if not repeats:
        lines.append(f"重演候选：无（相隔 ≥ {MOTION_GAP:g} 秒、差值 < {MOTION_SAME:g} 的相似帧没有连成段）")
    lines.append("读数低先看帧：大景别里又小又快的主体读数也低；渐变、闪光、淡入淡出也算运动")
    # 先登记进清单再写：写到一半失败，下次运行也能当自己的文件清掉
    own("motion.txt")
    (out / "motion.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    own("motion.json")
    (out / "motion.json").write_text(json.dumps({"fps": fps, "seg_frames": seg, "size": [w, h], "mean_motion": float(diffs.mean()),
                                                 "still_segments": n_still, "segments": segs, "holds": holds, "repeats": repeats},
                                                ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    log(f"运动量: 均值 {float(diffs.mean()):.1f}，近乎静止的半秒段 {n_still}/{len(segs)}，定住 {len(holds)} 处，"
        f"重演候选 {len(repeats)} 处（详见 motion.txt）")


def motion_step(ffmpeg, ffprobe, video, out, own, log):
    """运动量这一步的任何异常都只记一行，不影响抽帧的退出码。"""
    try:
        motion_report(ffmpeg, ffprobe, video, out, own, log)
    except Exception as e:   # noqa: BLE001 —— 附加产出，出什么错都不能拖垮原有的抽帧结果
        try:
            log(f"运动量: 失败（{type(e).__name__}: {e}），其他产出不受影响")
        except OSError:
            pass


def main(argv):
    if not argv:
        print(USAGE, file=sys.stderr)
        return 2
    video = argv[0]
    out = Path(argv[1] if len(argv) > 1 and argv[1] else os.path.splitext(video)[0] + "_frames")
    fps = argv[2] if len(argv) > 2 and argv[2] else "1"
    scene = argv[3] if len(argv) > 3 and argv[3] else "0.3"

    tools = {}
    for tool in ("ffmpeg", "ffprobe"):
        tools[tool] = find_tool(tool)
        if not tools[tool]:
            hint = "winget install Gyan.FFmpeg 或 choco install ffmpeg" if os.name == "nt" else "brew install ffmpeg"
            print(f"需要 {tool}（{hint}；或设环境变量 FFMPEG_DIR 指向它的 bin 目录）", file=sys.stderr)
            return 2
    ffmpeg, ffprobe = tools["ffmpeg"], tools["ffprobe"]
    if not os.path.isfile(video):
        print(f"找不到视频：{video}", file=sys.stderr)
        return 2
    try:
        out.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"建不了输出目录：{e}", file=sys.stderr)
        return 2

    # 只清理本脚本上一次记录在清单里的文件；目录里有同名但不是本脚本生成的文件时拒绝运行，避免混进旧图或误删
    manifest = out / ".aigc-frames.manifest"
    if manifest.is_file():
        names = manifest.read_text(encoding="utf-8").splitlines()
        if any(not OWNED_NAME_RE.match(f) for f in names):
            print("输出清单含非法文件名，停止清理", file=sys.stderr)
            return 2
        for f in names:
            try:
                (out / f).unlink()
            except FileNotFoundError:
                pass
        manifest.unlink()
    strangers = [n for n in FIXED_NAMES if (out / n).exists()]
    strangers += sorted(p.name for p in out.glob("sec_*.png")) + sorted(p.name for p in out.glob("cut_*.png"))
    if strangers:
        print(f"输出目录里有不是本脚本生成的同名文件：{' '.join(strangers)} ；换一个输出目录或自行移走", file=sys.stderr)
        return 2
    manifest.write_text("", encoding="utf-8")

    def own(name):
        with open(manifest, "a", encoding="utf-8", newline="\n") as f:
            f.write(name + "\n")

    run_txt = out / "run.txt"

    def log(line, echo=True):
        with open(run_txt, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        if echo:
            print(line)

    status = 0
    ver = run([ffmpeg, "-version"]).stdout.splitlines()
    run_txt.write_text(f"运行时间: {datetime.datetime.now():%Y-%m-%d %H:%M:%S}\n视频: {video}\n"
                       f"ffmpeg: {ver[0] if ver else ''}\n", encoding="utf-8")
    own("run.txt")
    p = run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", video])
    dur = p.stdout.strip() if p.returncode == 0 and p.stdout.strip() else "0"
    log(f"时长(秒): {dur}")

    # 首帧
    if run([ffmpeg, "-v", "error", "-y", "-i", video, "-frames:v", "1", str(out / "first.png")]).returncode == 0:
        own("first.png")
    else:
        log("首帧失败"); status = 2

    # 真正的最后一帧：从结尾前 1 秒起逐帧覆盖同一文件，留下的就是最后一个可解码帧；-copyts 让 showinfo 记录绝对时间
    p = run([ffmpeg, "-v", "info", "-nostats", "-y", "-sseof", "-1", "-copyts", "-i", video,
             "-vf", "showinfo", "-update", "1", str(out / "last.png")])
    times = PTS.findall(p.stderr)
    last_t = times[-1] if times else ""
    if (out / "last.png").is_file() and last_t:
        own("last.png"); own("last.txt")
        line = f"尾帧时间(秒): {last_t}（最后一个可解码帧）"
        (out / "last.txt").write_text(line + "\n", encoding="utf-8")
        log(line)
    else:
        log("尾帧失败（没有得到最后一帧或它的时间）"); status = 2

    # 每秒一帧
    if run([ffmpeg, "-v", "error", "-y", "-i", video, "-vf", f"fps={fps}", str(out / "sec_%03d.png")]).returncode == 0:
        for f in sec_files(out):
            own(f.name)
    else:
        log("抽样帧失败"); status = 2

    # 切镜检测：按当前 ffmpeg 支持的帧同步选项；失败时明确报告，不吞掉
    h = run([ffmpeg, "-hide_banner", "-h", "full"])
    sync = ["-fps_mode", "vfr"] if "fps_mode" in (h.stdout + h.stderr) else ["-vsync", "vfr"]
    own("cuts.txt")
    p = run([ffmpeg, "-v", "info", "-nostats", "-y", "-i", video, "-vf", f"select='gt(scene,{scene})',showinfo",
             *sync, str(out / "cut_%03d.png")])
    if p.returncode == 0:
        cuts = "".join(f"切镜时间点(秒): {t}\n" for t in PTS.findall(p.stderr))
        (out / "cuts.txt").write_text(cuts, encoding="utf-8")
        cut_imgs = sorted(x for x in out.glob("cut_*.png") if x.is_file())
        for f in cut_imgs:
            own(f.name)
        log(f"切镜检测: 成功，检出 {len(cut_imgs)} 处（阈值 {scene}；闪光可能被误判为切点，核对对应帧）")
        print(cuts, end="")
    else:
        log("切镜检测: 失败（原因见下），首尾帧与抽样帧仍可用")
        msg = "切镜检测失败，未生成 cut_*.png\n" + "".join(l + "\n" for l in p.stderr.splitlines()[-3:])
        (out / "cuts.txt").write_text(msg, encoding="utf-8")
        print(msg, end="")
        if status == 0:
            status = 3

    # 拼图
    n = len(sec_files(out))
    if n > 0:
        cols = 6
        rows = (n + cols - 1) // cols
        if run([ffmpeg, "-v", "error", "-y", "-i", str(out / "sec_%03d.png"), "-vf", f"scale=320:-1,tile={cols}x{rows}",
                str(out / "tile.png")]).returncode == 0:
            own("tile.png")
        else:
            log("拼图失败")
            if status == 0:
                status = 3

    # 运动量（v47）：缺 numpy 或失败只记一行，不改退出码
    motion_step(ffmpeg, ffprobe, video, out, own, log)

    log({0: "结果: 全部成功", 3: "结果: 部分成功（见上）"}.get(status, "结果: 失败"))
    print(f"输出目录: {out}")
    for name in sorted(x.name for x in out.iterdir() if not x.name.startswith(".")):
        print(name)
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
