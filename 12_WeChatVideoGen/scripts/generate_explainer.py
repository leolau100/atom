#!/usr/bin/env python3
# 生成"产品说明 / 科技产品展示"风格背景音乐(干净、现代、uplifting)
# 纯 ffmpeg 合成: 稀疏 bell 琶音 + 温暖 pad + 轻底鼓, 带空间混响
import subprocess

OUT = "/Users/liulei/Workbuddy/2026-09-03-21-25-37/magistrala-demo/remotion/public/bgm_explainer.mp3"
SR = 44100

# 8 秒动机(100 BPM, 每拍 0.6s), 铺满 16s 再循环到 ~132s
# (beat_offset, 频率Hz) —— C 大调五声, 稀疏 bell 音
motif = [
    (0.0, 523.25), (1.2, 659.25), (2.4, 783.99), (3.6, 659.25),
    (4.8, 587.33), (6.0, 783.99), (7.2, 659.25),
]
# 低音线(每 2 拍换一次根音)
bass = [
    (0.0, 130.81), (1.2, 110.00), (2.4, 87.31), (3.6, 98.00),
    (4.8, 130.81), (6.0, 110.00), (7.2, 87.31),
]

inputs = []   # 扁平 argv
labels = []   # 流标签
fc = []       # filter_complex 片段
n = 0

def add_input(src):
    inputs.extend(["-f", "lavfi", "-i", src])

def note_src(freq, dur, kind):
    if kind == "mel":
        expr = (f"0.55*sin(2*PI*{freq}*t)*sin(PI*t/{dur})"
                f"+0.22*sin(2*PI*{freq*2}*t)*sin(PI*t/{dur})"
                f"+0.10*sin(2*PI*{freq*3}*t)*sin(PI*t/{dur})")
        return f"aevalsrc={expr}:d={dur}:s={SR}"
    if kind == "bass":
        expr = f"0.5*sin(2*PI*{freq}*t)"
        return f"aevalsrc={expr}:d={dur}:s={SR}"
    # kick
    expr = f"0.7*sin(2*PI*{freq}*t)*exp(-t*10)"
    return f"aevalsrc={expr}:d={dur}:s={SR}"

# 旋律
for rep in range(2):
    base = rep * 8.0
    for (off, f) in motif:
        t = round(base + off, 3)
        add_input(note_src(f, 1.1, 'mel'))
        labels.append(f"[m{n}]")
        fc.append(f"[{n}]adelay=delays={int(t*1000)}[m{n}]")
        n += 1
# 低音
for rep in range(2):
    base = rep * 8.0
    for (off, f) in bass:
        t = round(base + off, 3)
        add_input(note_src(f, 1.15, 'bass'))
        labels.append(f"[b{n}]")
        fc.append(f"[{n}]adelay=delays={int(t*1000)}[b{n}]")
        n += 1
# 轻底鼓 每 1.2s
for t in [round(i*1.2, 3) for i in range(14)]:
    add_input(note_src(55.0, 0.35, 'kick'))
    labels.append(f"[k{n}]")
    fc.append(f"[{n}]adelay=delays={int(t*1000)}[k{n}]")
    n += 1
# 温暖 pad (C 大三和弦, 慢颤音)
pad_expr = ("0.18*sin(2*PI*130.81*t)+0.14*sin(2*PI*164.81*t)+0.12*sin(2*PI*196.00*t)")
add_input(f"aevalsrc={pad_expr}:d=16.0:s={SR}")
labels.append("[pad]")
fc.append(f"[{n}]atrim=start=0:end=16.0,tremolo=f=0.2:d=0.5[pad]")
n += 1

all_labels = "".join(labels)
fc.append(f"{all_labels}amix=inputs={n}:duration=longest[mx]")
fc.append("[mx]aecho=0.85:0.9:55|110:0.35|0.18[rv]")
fc.append("[rv]lowpass=f=3200,volume=1.6[warm]")
fc.append("[warm]aloop=loop=7:size=2e9[lp]")
fc.append("[lp]atrim=start=0:end=132,afade=t=in:st=0:d=2,afade=t=out:st=128:d=4[aout]")
fc_str = ";".join(fc)

cmd = ["/opt/homebrew/bin/ffmpeg", "-y"] + inputs + \
      ["-filter_complex", fc_str, "-map", "[aout]",
       "-c:a", "libmp3lame", "-b:a", "160k", OUT]
print("inputs:", n)
r = subprocess.run(cmd, capture_output=True, text=True)
print("rc:", r.returncode)
print(r.stderr[-1200:])
