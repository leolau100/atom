#!/usr/bin/env python3
"""手动指定区域推进（Pan&Zoom）：在关键操作处把画面裁切放大到指定区域。
用法：
  python3 apply_zoom.py -i seg/c4.mp4 -o seg/c4_zoomed.mp4 -s zoom.json
zoom.json 示例：
  [
    {"start": 2.0, "end": 4.0, "cx": 1050, "cy": 620, "zoom": 1.6},
    {"start": 5.0, "end": 7.0, "cx": 1080, "cy": 720, "zoom": 1.5}
  ]
"""
import os, sys, json, subprocess, argparse, tempfile, shutil

FF = '/opt/homebrew/bin/ffmpeg'
FP = '/opt/homebrew/bin/ffprobe'
W, H = 1600, 1000


def probe_duration(path):
    r = subprocess.run([FP, '-v', 'error', '-show_entries', 'format=duration',
                        '-of', 'json', path], capture_output=True, text=True)
    return float(json.loads(r.stdout)['format']['duration'])


def run(cmd):
    print('+', ' '.join(cmd[:6]) + ' ...')
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print('STDERR:', r.stderr[-2000:])
        sys.exit(1)
    return r


def clip(v, lo, hi):
    return max(lo, min(hi, v))


def build_segments(total, specs, trans=0.3):
    """把总长和 zoom 区间拆成 full/zoom_in/hold/zoom_out 片段。"""
    specs = sorted(specs, key=lambda z: z['start'])
    segs = []
    prev_end = 0.0
    for z in specs:
        s = float(z['start']); e = float(z['end'])
        cx = clip(float(z['cx']), 0, W)
        cy = clip(float(z['cy']), 0, H)
        zoom = max(1.0, float(z.get('zoom', 1.5)))
        if e <= s:
            continue
        # full before
        full_end = s - trans
        if full_end > prev_end + 0.05:
            segs.append({'type': 'full', 'ss': prev_end,
                         'dur': full_end - prev_end})
        # zoom in
        segs.append({'type': 'zoom_in', 'ss': max(0, s - trans),
                     'dur': trans, 'cx': cx, 'cy': cy, 'zoom': zoom})
        # zoom hold
        segs.append({'type': 'zoom_hold', 'ss': s,
                     'dur': e - s, 'cx': cx, 'cy': cy, 'zoom': zoom})
        # zoom out
        segs.append({'type': 'zoom_out', 'ss': e,
                     'dur': trans, 'cx': cx, 'cy': cy, 'zoom': zoom})
        prev_end = e + trans
    # full tail
    if total - prev_end > 0.05:
        segs.append({'type': 'full', 'ss': prev_end,
                     'dur': total - prev_end})
    return segs


def render_segment(src, seg, out):
    t = seg['type']
    ss = seg['ss']; dur = seg['dur']
    if t == 'full':
        run([FF, '-y', '-i', src, '-ss', str(ss), '-t', str(dur),
             '-vf', 'scale=1600:1000:flags=lanczos,setsar=1', '-an',
             '-r', '30', '-c:v', 'libx264', '-crf', '18',
             '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out])
        return
    cx, cy, zoom = seg['cx'], seg['cy'], seg['zoom']
    wz = W / zoom; hz = H / zoom
    cx = clip(cx, wz / 2, W - wz / 2)
    cy = clip(cy, hz / 2, H - hz / 2)
    d = dur
    FPS = 30
    if t == 'zoom_hold':
        x = cx - wz / 2; y = cy - hz / 2
        vf = f"crop={wz}:{hz}:{x}:{y},scale=1600:1000:flags=lanczos,setsar=1"
    elif t in ('zoom_in', 'zoom_out'):
        # zoompan: 输入输出 1:1, d=1, 用 on 做线性插值
        n = max(1, int(round(dur * FPS)) - 1)
        if t == 'zoom_in':
            z_expr = f"1+({zoom-1})*(on/{n})"
            cx_expr = f"{W/2}+({cx-W/2})*(on/{n})"
            cy_expr = f"{H/2}+({cy-H/2})*(on/{n})"
        else:
            z_expr = f"{zoom}-({zoom-1})*(on/{n})"
            cx_expr = f"{cx}+({W/2-cx})*(on/{n})"
            cy_expr = f"{cy}+({H/2-cy})*(on/{n})"
        x_expr = f"max(0,min({W}-({W}/{z_expr}),{cx_expr}-({W}/(2*{z_expr}))))"
        y_expr = f"max(0,min({H}-({H}/{z_expr}),{cy_expr}-({H}/(2*{z_expr}))))"
        vf = (f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}':"
              f"d=1:s={W}x{H}:fps={FPS},format=yuv420p,setsar=1")
    else:
        raise ValueError(t)
    run([FF, '-y', '-i', src, '-ss', str(ss), '-t', str(dur),
         '-vf', vf, '-an', '-r', '30', '-c:v', 'libx264', '-crf', '18',
         '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-i', '--input', required=True)
    ap.add_argument('-o', '--output', required=True)
    ap.add_argument('-s', '--spec', required=True)
    ap.add_argument('-t', '--transition', type=float, default=0.3)
    a = ap.parse_args()
    total = probe_duration(a.input)
    specs = json.load(open(a.spec))
    segs = build_segments(total, specs, a.transition)
    tmpdir = tempfile.mkdtemp(prefix='zoom_')
    try:
        files = []
        for i, seg in enumerate(segs):
            out = os.path.join(tmpdir, f'seg_{i:03d}.mp4')
            render_segment(a.input, seg, out)
            files.append(out)
        # concat filter
        inputs = sum([['-i', f] for f in files], [])
        n = len(files)
        complex_f = ''.join([f'[{i}:v]' for i in range(n)]) + \
                    f'concat=n={n}:v=1:a=0[outv]'
        run([FF, '-y'] + inputs +
            ['-filter_complex', complex_f, '-map', '[outv]',
             '-r', '30', '-c:v', 'libx264', '-crf', '18',
             '-pix_fmt', 'yuv420p', '-movflags', '+faststart', a.output])
        print('ZOOMED ->', a.output, 'dur=', probe_duration(a.output))
    finally:
        shutil.rmtree(tmpdir)


if __name__ == '__main__':
    main()
