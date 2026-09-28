// 阅读页朗读的播放器（docs/06 第 8.2 节）。
//
// iPad Safari 只允许在用户点击时开始播放声音，所以统一用 Web Audio：整个应用共用一个 AudioContext，
// 在孩子的第一次点击里（书架上点书、点小喇叭、打开自动朗读）解锁；解锁后翻页自动朗读就不再受限。
// 播放器是模块级单例：从书架进入阅读页不会重新创建，iOS 对 AudioContext 的数量也有限制。

type Listener = (playingUrl: string | null) => void;

let context: AudioContext | null = null;
const buffers = new Map<string, Promise<AudioBuffer>>();
const listeners = new Set<Listener>();
let source: AudioBufferSourceNode | null = null;
let playingUrl: string | null = null;
// 每次开始或停止播放都加 1，旧的播放序列看到编号变了就不再继续
let generation = 0;

function getContext(): AudioContext | null {
  if (context) return context;
  const Ctor =
    window.AudioContext ??
    (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Ctor) return null;
  context = new Ctor();
  return context;
}

/** 在用户点击的事件处理函数里调用：创建 / 恢复 AudioContext，并播放一段静音完成 iOS 的解锁 */
export function unlockStoryAudio() {
  const ctx = getContext();
  if (!ctx) return;
  if (ctx.state === "suspended") void ctx.resume();
  const silent = ctx.createBufferSource();
  silent.buffer = ctx.createBuffer(1, 1, 22050);
  silent.connect(ctx.destination);
  silent.start(0);
}

function load(url: string): Promise<AudioBuffer> {
  let buffer = buffers.get(url);
  if (!buffer) {
    const ctx = getContext();
    if (!ctx) return Promise.reject(new Error("浏览器不支持播放声音"));
    buffer = fetch(url, { credentials: "same-origin" })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.arrayBuffer();
      })
      .then((data) => ctx.decodeAudioData(data));
    // 失败的不缓存，下次再试
    buffer.catch(() => buffers.delete(url));
    buffers.set(url, buffer);
  }
  return buffer;
}

function setPlaying(url: string | null) {
  playingUrl = url;
  listeners.forEach((listener) => listener(url));
}

export function stopStoryAudio() {
  generation++;
  if (source) {
    source.onended = null;
    try {
      source.stop();
    } catch {
      // 已经停止
    }
    source = null;
  }
  if (playingUrl !== null) setPlaying(null);
}

/** 依次播放几段朗读（对开时两页按朗读顺序连读），会先停止正在播放的 */
export async function playStoryAudio(urls: string[]) {
  stopStoryAudio();
  const current = generation;
  const ctx = getContext();
  if (!ctx) return;
  for (const url of urls) {
    let buffer: AudioBuffer;
    try {
      buffer = await load(url);
    } catch {
      continue; // 一段加载失败就跳过，接着读下一段
    }
    if (generation !== current) return;
    if (ctx.state === "suspended") await ctx.resume().catch(() => undefined);
    const node = ctx.createBufferSource();
    node.buffer = buffer;
    node.connect(ctx.destination);
    source = node;
    setPlaying(url);
    const ended = new Promise<void>((resolve) => (node.onended = () => resolve()));
    node.start();
    await ended;
    if (generation !== current) return;
    source = null;
  }
  if (generation === current) setPlaying(null);
}

/** 提前下载并解码，翻到这页时能立刻播放 */
export function preloadStoryAudio(urls: string[]) {
  if (!context) return; // 还没解锁时不创建 AudioContext
  urls.forEach((url) => void load(url).catch(() => undefined));
}

export function subscribeStoryAudio(listener: Listener) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function getPlayingStoryAudio() {
  return playingUrl;
}
