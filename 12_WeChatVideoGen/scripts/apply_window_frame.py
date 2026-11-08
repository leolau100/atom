#!/usr/bin/env python3
# 给录屏片段套上 macOS 窗口外观：把视频等比缩放后嵌入窗口内容区，再 overlay 到窗口框架上。
# 依赖同目录的 gen_window_frame.py（生成框架）。
# 用法: python3 apply_window_frame.py -i seg/c4.mp4 -o seg/c4_win.mp4 \
#        --title "ModbusSim REST API — Swagger UI"
# 复用同一张框架（多段视频共用，避免重复生成）: --frame /path/frame.png
import argparse, os, subprocess, sys, tempfile

FF = '/opt/homebrew/bin/ffmpeg'
FP = '/opt/homebrew/bin/ffprobe'
GEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gen_window_frame.py')

W, H = 1600, 1000
WIN_W, WIN_H, BAR_H = 1360, 900, 48
WX, WY = (W - WIN_W) // 2, (H - WIN_H) // 2
CONTENT_W, CONTENT_H = WIN_W, WIN_H - BAR_H        # 1360 × 852
OX, OY = WX, WY + BAR_H                            # 120, 98


def probe_size(path):
    r = subprocess.run([FP, '-v', 'error', '-select_streams', 'v:0',
                        '-show_entries', 'stream=width,height', '-of', 'csv=p=0', path],
                       capture_output=True, text=True)
    w, h = r.stdout.strip().split(',')
    return int(w), int(h)


def make_frame(title, path):
    subprocess.run([sys.executable, GEN, '--frame-only',
                    '--output', path, '--title', title], check=True)
    return path


def apply_frame(src, dst, title, frame=None):
    tmp_frame = frame
    own = False
    if not tmp_frame:
        tmp_frame = os.path.join(tempfile.gettempdir(), f'_winframe_{os.getpid()}.png')
        make_frame(title, tmp_frame)
        own = True

    sw, sh = probe_size(src)
    s = min(CONTENT_W / sw, CONTENT_H / sh)
    nw, nh = int(sw * s), int(sh * s)
    x = OX + (CONTENT_W - nw) // 2
    y = OY + (CONTENT_H - nh) // 2

    cmd = [FF, '-y', '-i', src,
           '-loop', '1', '-framerate', '30', '-i', tmp_frame,
           '-filter_complex',
           (f'[0:v]scale={nw}:{nh}:flags=lanczos,setsar=1[vid];'
            f'[1:v][vid]overlay={x}:{y}:shortest=1[out]'),
           '-map', '[out]', '-c:v', 'libx264', '-crf', '18',
           '-pix_fmt', 'yuv420p', '-r', '30', '-movflags', '+faststart', dst]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print('STDERR:', r.stderr[-2500:])
        sys.exit(1)
    if own:
        try:
            os.remove(tmp_frame)
        except OSError:
            pass
    return dst


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('-i', '--input', required=True)
    ap.add_argument('-o', '--output', required=True)
    ap.add_argument('--title', default='')
    ap.add_argument('--frame', default=None, help='复用已有的窗口框架 PNG')
    a = ap.parse_args()
    apply_frame(a.input, a.output, a.title, a.frame)
    print('WINDOWED ->', a.output)
