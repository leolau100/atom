// 文档站内容组织（按分类精选核心文章）
export const categories = [
  { key: 'platform', name: '物联网平台', desc: '开源 IoT 平台与工业数采' },
  { key: 'protocol', name: '工业协议', desc: 'IEC / DLT 等标准协议与仿真' },
  { key: 'tool', name: '工具链', desc: '工控与调试利器' },
  { key: 'future', name: '新纪元', desc: 'AI 与前沿玩法' },
]

export const articles = [
  { slug: 'thinger-io', cat: 'platform', title: 'Thinger.io 开源物联网平台', file: 'iot-content/thinger-io/index.md', tag: 'IoT Platform' },
  { slug: 'iotsharp', cat: 'platform', title: 'IoTSharp —— .NET 开源物联网平台', file: 'iot-content/iotsharp/index.md', tag: '.NET' },
  { slug: 'neoindustrial', cat: 'platform', title: 'NeoIndustrial —— 自研工业数采平台', file: 'iot-content/neoindustrial/index.md', tag: '自研 · 工业数采', featured: true },
  { slug: 'fledge', cat: 'platform', title: 'Fledge —— LF Edge 工业边缘框架', file: 'iot-content/fledge/index.md', tag: 'Edge' },
  { slug: 'iec104', cat: 'protocol', title: 'IEC 60870-5-104 协议与模拟器', file: 'iot-content/iec104/index.md', tag: 'IEC104' },
  { slug: 'dlt698', cat: 'protocol', title: 'DLT698.45 电力协议及测试工具资源库', file: 'iot-content/dlt698/index.md', tag: 'DLT698' },
  { slug: 'dlt645', cat: 'protocol', title: 'DLT645 电能表协议仿真', file: 'iot-content/dlt645/index.md', tag: 'DLT645' },
  { slug: 'top10-tools', cat: 'tool', title: '工控人必备十大工具', file: 'iot-content/top10-tools/index.md', tag: '工具' },
  { slug: 'modbus-sim', cat: 'tool', title: 'Modbus 模拟器盘点（soso7885）', file: 'iot-content/modbus-sim/index.md', tag: 'Modbus' },
  { slug: 'gpt6', cat: 'future', title: 'GPT-6 跨领域玩法盘点', file: 'iot-content/gpt6/index.md', tag: 'AI' },
]

export function categoryByKey(key) {
  return categories.find((c) => c.key === key)
}
export function articlesByCat(key) {
  return articles.filter((a) => a.cat === key)
}
export function articleBySlug(slug) {
  return articles.find((a) => a.slug === slug)
}
