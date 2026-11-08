#!/usr/bin/env python3
import subprocess, os

OUT = '/Users/liulei/Workbuddy/2026-09-03-21-25-37/magistrala-demo/remotion/public/bgm.mp3'
FF = '/opt/homebrew/bin/ffmpeg'

# 欢快 C 大调旋律 (八分音符, 0.25s/个, 4s 循环, 16 个音)
MEL = [329.63, 392.00, 523.25, 392.00, 349.23, 440.00, 523.25, 440.00,
       329.63, 392.00, 587.33, 392.00, 293.66, 349.23, 440.00, 392.00]
# 低音 (四分音符, 0.5s/个, 4s 循环, 8 个音)
BASS = [130.81, 196.00, 130.81, 196.00, 174.61, 130.81, 196.00, 196.00]
# 铺底和弦 Cadd9 (4s 持续)
PAD = [261.63, 329.63, 392.00, 587.33]
MELODY_D = 0.25
BASS_D = 0.50

input_cmds = []   # each: ['-f','lavfi','-i', expr]
parts = []        # filter_complex parts
idx = 0

# --- melody ---
mel_nodes = []
for f in MEL:
    input_cmds.append(['-f', 'lavfi', '-i', f"sine=f={f}:d={MELODY_D}:r=44100"])
    parts.append(f"[{idx}:a]afade=t=in:st=0:d=0.01,afade=t=out:st={MELODY_D-0.06:.2f}:d=0.06,volume=0.38[m{idx}]")
    mel_nodes.append(f"[m{idx}]")
    idx += 1
parts.append("".join(mel_nodes) + f"concat=n={len(mel_nodes)}:v=0:a=1[m]")

# --- bass ---
bass_nodes = []
for f in BASS:
    input_cmds.append(['-f', 'lavfi', '-i', f"sine=f={f}:d={BASS_D}:r=44100"])
    parts.append(f"[{idx}:a]afade=t=in:st=0:d=0.01,afade=t=out:st={BASS_D-0.08:.2f}:d=0.08,volume=0.30[b{idx}]")
    bass_nodes.append(f"[b{idx}]")
    idx += 1
parts.append("".join(bass_nodes) + f"concat=n={len(bass_nodes)}:v=0:a=1[b]")

# --- pad ---
pad_nodes = []
for f in PAD:
    input_cmds.append(['-f', 'lavfi', '-i', f"sine=f={f}:d=4:r=44100"])
    parts.append(f"[{idx}:a]volume=0.10[pd{idx}]")
    pad_nodes.append(f"[pd{idx}]")
    idx += 1
parts.append("".join(pad_nodes) + f"amix=inputs={len(pad_nodes)}:duration=longest[p]")

# --- kick (8 底鼓, 定位到 k*0.5s) ---
kick_nodes = []
for k in range(8):
    t = k * 0.5
    input_cmds.append(['-f', 'lavfi', '-i', "sine=f=110:d=0.18:r=44100"])
    parts.append(f"[{idx}:a]afade=t=out:st=0.02:d=0.14,volume=0.55,adelay=delays={int(t*1000)}:all=1[k{idx}]")
    kick_nodes.append(f"[k{idx}]")
    idx += 1
parts.append("".join(kick_nodes) + f"amix=inputs={len(kick_nodes)}:duration=longest[kt]")

# --- hat (8 踩镲, 定位到 0.25+k*0.5s) ---
hat_nodes = []
for k in range(8):
    t = 0.25 + k * 0.5
    input_cmds.append(['-f', 'lavfi', '-i', "anoisesrc=d=0.05:r=44100:c=pink"])
    parts.append(f"[{idx}:a]highpass=f=6000,afade=t=out:st=0.01:d=0.04,volume=0.12,adelay=delays={int(t*1000)}:all=1[h{idx}]")
    hat_nodes.append(f"[h{idx}]")
    idx += 1
parts.append("".join(hat_nodes) + f"amix=inputs={len(hat_nodes)}:duration=longest[ht]")

# 叠加所有层 + 循环填充 132s + 低通提亮 + 限幅 + 首尾淡入淡出
parts.append("[m][b][p][kt][ht]amix=inputs=5:duration=longest[mix]")
parts.append("[mix]aloop=loop=40:size=2e9[lp]")
parts.append("[lp]atrim=0:132,lowpass=f=9000,volume=1.6,alimiter=limit=0.95,afade=t=in:st=0:d=1.5,afade=t=out:st=128:d=4[out]")

filter_complex = ";".join(parts)

cmd = [FF, '-y']
for inp in input_cmds:
    cmd += inp
cmd += ['-filter_complex', filter_complex, '-map', '[out]', '-c:a', 'libmp3lame', '-b:a', '128k', OUT]

print('inputs:', len(input_cmds))
r = subprocess.run(cmd, capture_output=True, text=True)
print('returncode', r.returncode)
if r.returncode != 0:
    print(r.stderr[-2500:])
else:
    print('OK ->', OUT)
