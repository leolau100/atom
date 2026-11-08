#!/usr/bin/env python3
import subprocess, os, json, sys

# 项目根目录(含 videos/raw-0*、cards/、remotion/、output/)
# 可用环境变量 DEMO_ROOT 覆盖, 便于在不同机器/目录复用
ROOT = os.environ.get('DEMO_ROOT', '/Users/liulei/Workbuddy/2026-09-03-21-25-37/magistrala-demo')
SEG = os.path.join(ROOT, 'seg')
CARDS = os.path.join(ROOT, 'cards')
BGM = os.path.join(ROOT, 'remotion', 'public', 'bgm.mp3')
OUT_NOSOUND = os.path.join(ROOT, 'out_nosound.mp4')
OUT_FINAL = os.path.join(ROOT, 'output', 'magistrala-demo-final.mp4')
os.makedirs(SEG, exist_ok=True)
os.makedirs(os.path.dirname(OUT_FINAL), exist_ok=True)

FF = '/opt/homebrew/bin/ffmpeg'
FP = '/opt/homebrew/bin/ffprobe'

def probe_duration(path):
    r = subprocess.run([FP, '-v','error','-show_entries','format=duration','-of','json',path],
                       capture_output=True, text=True)
    return float(json.loads(r.stdout)['format']['duration'])

def run(cmd):
    print('+', ' '.join(cmd[:6]), '...')
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print('STDERR:', r.stderr[-1500:])
        sys.exit(1)
    return r

# 1) speed up raw clips 1.5x -> seg/clipN.mp4
raw = [
    ('c1', 'videos/raw-01-login'),
    ('c2', 'videos/raw-02-workspace'),
    ('c3', 'videos/raw-03-device'),
    ('c4', 'videos/raw-04-channel'),
    ('c5', 'videos/raw-05-connect'),
    ('c6', 'videos/raw-06-final'),
]
for name, d in raw:
    src = os.path.join(ROOT, d, os.listdir(os.path.join(ROOT,d))[0])
    dst = os.path.join(SEG, f'{name}.mp4')
    if not os.path.exists(dst):
        run([FF,'-y','-i',src,
             '-vf','scale=1600:1000:flags=lanczos,setsar=1,setpts=0.6666667*PTS',
             '-an','-r','30','-c:v','libx264','-crf','18','-pix_fmt','yuv420p',
             '-movflags','+faststart',dst])

# 2) card images -> seg card videos
card_durs = {'intro':5, 't1':5,'t2':5,'t3':5,'t4':5,'t5':5,'t6':5,'outro':5}
for key, dur in card_durs.items():
    src = os.path.join(CARDS, f'{key}.png')
    dst = os.path.join(SEG, f'{key}.mp4')
    if not os.path.exists(dst):
        run([FF,'-y','-loop','1','-i',src,'-t',str(dur),
             '-vf','scale=1600:1000:flags=lanczos,setsar=1','-r','30',
             '-c:v','libx264','-crf','18','-pix_fmt','yuv420p',
             '-movflags','+faststart',dst])

# 3) build segment order with durations
order = [
    ('intro',), ('t1',), ('c1',), ('t2',), ('c2',), ('t3',), ('c3',),
    ('t4',), ('c4',), ('t5',), ('c5',), ('t6',), ('c6',), ('outro',),
]
seg_paths = []
durs = []
for (name,) in order:
    p = os.path.join(SEG, f'{name}.mp4')
    seg_paths.append(p)
    durs.append(card_durs[name] if name in card_durs else probe_duration(p))

n = len(seg_paths)
T = 0.5  # transition duration

# 4) build xfade filter
parts = []
# prefix sum of D0..D_{i-1}
prefix = 0.0
# first join
offset = durs[0] - T
parts.append(f"[0:v][1:v]xfade=transition=fade:duration={T}:offset={offset:.4f}[v1]")
prev = '[v1]'
prefix = durs[0]
for i in range(2, n):
    prefix += durs[i-1]            # now sum D0..D_{i-1}
    offset = prefix - i*T
    lbl = f'[v{i}]' if i < n-1 else '[vout]'
    parts.append(f"{prev}[{i}:v]xfade=transition=fade:duration={T}:offset={offset:.4f}{lbl}")
    prev = lbl

total = sum(durs) - (n-1)*T
# fade in/out at very ends
parts.append(f"{prev}fade=t=in:st=0:d=0.4,fade=t=out:st={total-0.4:.4f}:d=0.4[vout]")
filter_complex = ';'.join(parts)

# 5) render video-only (no audio) with xfade
cmd = [FF,'-y']
for p in seg_paths:
    cmd += ['-i', p]
cmd += ['-filter_complex', filter_complex,
        '-map','[vout]','-c:v','libx264','-crf','18','-pix_fmt','yuv420p',
        '-r','30','-movflags','+faststart', OUT_NOSOUND]
run(cmd)
print('NOSOUND duration:', probe_duration(OUT_NOSOUND))

# 6) mux background music
cmd2 = [FF,'-y','-i',OUT_NOSOUND,'-i',BGM,
        '-filter_complex','[1:a]volume=0.4[a]',
        '-map','0:v','-map','[a]','-c:v','copy','-c:a','aac','-b:a','128k',
        '-shortest', OUT_FINAL]
run(cmd2)
print('FINAL:', OUT_FINAL, 'dur=', probe_duration(OUT_FINAL))
