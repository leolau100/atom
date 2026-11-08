import React from 'react';
import { AbsoluteFill, Sequence, Video, Audio, staticFile, useCurrentFrame, interpolate } from 'remotion';

const FPS = 30;
const SPEED = 1.5;
const TITLE_DUR = Math.round(90 / SPEED); // 60
const INTRO_DUR = Math.round(180 / SPEED); // 120
const OUTRO_DUR = Math.round(180 / SPEED); // 120

// 原始 webm 时长(秒)来自 ffprobe,按 SPEED 加速后换算为帧数
const clipSeconds = [22.760, 30.040, 30.960, 22.920, 28.880, 28.640];
const clipDurations = clipSeconds.map((s) => Math.round((s / SPEED) * FPS));

const CLIPS = [
  {
    id: 'clip01',
    title: '01 登录 Magistrala 平台',
    subtitle: '访问本地部署的 Magistrala, 使用管理员账号进入控制台',
    dur: clipDurations[0],
    src: 'videos/clip01.webm',
  },
  {
    id: 'clip02',
    title: '02 新建 Smart Factory 工作区',
    subtitle: '在工作区模块创建名为 Smart Factory 的工作空间',
    dur: clipDurations[1],
    src: 'videos/clip02.webm',
  },
  {
    id: 'clip03',
    title: '03 添加温度传感器设备',
    subtitle: '创建设备 Temp Sensor 01 并查看连接凭证',
    dur: clipDurations[2],
    src: 'videos/clip03.webm',
  },
  {
    id: 'clip04',
    title: '04 创建 telemetry 数据通道',
    subtitle: '新建 telemetry 通道用于接收设备遥测消息',
    dur: clipDurations[3],
    src: 'videos/clip04.webm',
  },
  {
    id: 'clip05',
    title: '05 连接设备到通道',
    subtitle: '将 Temp Sensor 01 订阅至 telemetry 通道',
    dur: clipDurations[4],
    src: 'videos/clip05.webm',
  },
  {
    id: 'clip06',
    title: '06 发送遥测消息',
    subtitle: '通过消息页面向通道发送 temperature=26.5',
    dur: clipDurations[5],
    src: 'videos/clip06.webm',
  },
];

const COMMON_STYLE = {
  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif',
};

function FadeIn({ children, duration = 15 }) {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, duration], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  return <div style={{ opacity }}>{children}</div>;
}

function SlideUp({ children, duration = 20 }) {
  const frame = useCurrentFrame();
  const y = interpolate(frame, [0, duration], [20, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const opacity = interpolate(frame, [0, duration], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  return (
    <div style={{ opacity, transform: `translateY(${y}px)` }}>
      {children}
    </div>
  );
}

function CenteredText({ title, subtitle, titleSize = 64, subtitleSize = 32, subtitleColor = '#94a3b8' }) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        textAlign: 'center',
        gap: 24,
        width: '100%',
        maxWidth: 1400,
        padding: 40,
      }}
    >
      <SlideUp>
        <div
          style={{
            fontSize: titleSize,
            fontWeight: 800,
            lineHeight: 1.2,
            color: '#f8fafc',
          }}
        >
          {title}
        </div>
      </SlideUp>
      <FadeIn duration={Math.round(20 / SPEED)}>
        <div
          style={{
            fontSize: subtitleSize,
            color: subtitleColor,
            lineHeight: 1.5,
          }}
        >
          {subtitle}
        </div>
      </FadeIn>
    </div>
  );
}

function TitleCard({ title, subtitle }) {
  return (
    <AbsoluteFill
      style={{
        ...COMMON_STYLE,
        background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <CenteredText title={title} subtitle={subtitle} />
    </AbsoluteFill>
  );
}

function Intro() {
  return (
    <AbsoluteFill
      style={{
        ...COMMON_STYLE,
        background: 'linear-gradient(135deg, #020617 0%, #0f172a 100%)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <CenteredText
        title="Magistrala 开源物联网平台"
        subtitle="6 分钟快速上手指南"
        titleSize={72}
        subtitleSize={40}
        subtitleColor="#38bdf8"
      />
      <FadeIn duration={Math.round(40 / SPEED)}>
        <div
          style={{
            position: 'absolute',
            bottom: 80,
            width: '100%',
            textAlign: 'center',
            fontSize: 28,
            color: '#94a3b8',
          }}
        >
          登录 · 工作区 · 设备 · 通道 · 连接 · 发消息
        </div>
      </FadeIn>
    </AbsoluteFill>
  );
}

function Outro() {
  return (
    <AbsoluteFill
      style={{
        ...COMMON_STYLE,
        background: 'linear-gradient(135deg, #0f172a 0%, #020617 100%)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <CenteredText
        title="演示结束"
        subtitle="Magistrala 提供设备管理、消息总线与规则引擎, 是构建 IoT 平台的完整开源方案。"
        titleSize={72}
        subtitleSize={32}
      />
    </AbsoluteFill>
  );
}

function Clip({ src }) {
  return (
    <FadeIn duration={Math.round(12 / SPEED)}>
      <AbsoluteFill>
        <Video
          src={staticFile(src)}
          playbackRate={SPEED}
          style={{ width: '100%', height: '100%', objectFit: 'contain' }}
        />
      </AbsoluteFill>
    </FadeIn>
  );
}

export function VideoComposition() {
  let cursor = 0;
  const blocks = [];

  blocks.push({ type: 'intro', from: cursor, dur: INTRO_DUR });
  cursor += INTRO_DUR;

  for (const c of CLIPS) {
    blocks.push({ type: 'title', from: cursor, dur: TITLE_DUR, title: c.title, subtitle: c.subtitle });
    cursor += TITLE_DUR;
    blocks.push({ type: 'clip', from: cursor, dur: c.dur, src: c.src });
    cursor += c.dur;
  }

  blocks.push({ type: 'outro', from: cursor, dur: OUTRO_DUR });
  cursor += OUTRO_DUR;

  const totalDuration = cursor;

  return (
    <AbsoluteFill>
      <Audio src={staticFile('bgm.mp3')} volume={0.4} />
      {blocks.map((b, i) => (
        <Sequence key={i} from={b.from} durationInFrames={b.dur} layout="absolute-fill">
          {b.type === 'intro' && <Intro />}
          {b.type === 'title' && <TitleCard title={b.title} subtitle={b.subtitle} />}
          {b.type === 'clip' && <Clip src={b.src} />}
          {b.type === 'outro' && <Outro />}
        </Sequence>
      ))}
    </AbsoluteFill>
  );
}

export const TOTAL_FRAMES = INTRO_DUR + OUTRO_DUR + CLIPS.length * TITLE_DUR + clipDurations.reduce((a, b) => a + b, 0);
