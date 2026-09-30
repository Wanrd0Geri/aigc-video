#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_frames.py <视频> [输出目录] [每秒帧数] [切镜阈值]   （跨平台版，macOS 与 Windows 通用；extract_frames.sh 只是转调本脚本）
产出：first.png（第一帧）、last.png（真正的最后一个可解码帧，时间写在 last.txt）、sec_%03d.png（每秒一帧）、
      cut_%03d.png（切镜检测，阈值默认 0.3）、cuts.txt（切点时间或失败原因）、tile.png（拼图）、run.txt（本次运行记录）、
      .aigc-frames.manifest（本脚本生成过的文件清单，重复运行只清理清单里的文件）
退出码：0 全部成功；2 缺依赖、输入错误或首尾帧失败；3 部分成功（切镜检测或拼图失败，已生成的图保留，run.txt 写明）
证据边界：抽帧只能定位切点与状态；正常速度的节奏、接触瞬间、声音关系要连续播放和听审，拼图证明不了。
ffmpeg / ffprobe 查找顺序：PATH → 环境变量 FFMPEG_DIR → 常见安装位置（/opt/homebrew/bin、/usr/local/bin；Windows 的 C:\\ffmpeg\\bin 等）。
"""
import datetime, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

USAGE = "用法: extract_frames.py <视频> [输出目录] [每秒帧数] [切镜阈值]"
OWNED_NAME_RE = re.compile(r"^(first\.png|last\.png|last\.txt|tile\.png|cuts\.txt|run\.txt|(sec|cut)_[0-9]+\.png)$")
FIXED_NAMES = ("first.png", "last.png", "last.txt", "tile.png", "cuts.txt", "run.txt")
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

    log({0: "结果: 全部成功", 3: "结果: 部分成功（见上）"}.get(status, "结果: 失败"))
    print(f"输出目录: {out}")
    for name in sorted(x.name for x in out.iterdir() if not x.name.startswith(".")):
        print(name)
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
