// 我的所有产品 / 项目
export const products = [
  {
    name: 'NiceWeChatFile',
    tagline: '微信公众号 Markdown 编辑器',
    description:
      '写完 Markdown 一键生成微信兼容的内联样式 HTML，直接粘贴到公众号。内置 64 款主题，支持顶部/底部品牌模版，本地自动保存，亦可作 Chrome 插件使用。',
    url: 'https://hackertodo.com/md',
    github: 'https://github.com/leolau100/WeChatFile',
    tags: ['Vue3', 'Vite', 'Markdown', 'Chrome 插件'],
    status: '已上线',
    published: '2026-06-23',
  },
  {
    name: 'Happy English',
    tagline: '英语学习应用',
    description:
      '面向英语学习者的前后端分离应用，帮助更高效地积累与练习英语内容。',
    url: 'https://hackertodo.com/happy',
    github: '',
    tags: ['Web 应用', '前后端分离'],
    status: '已上线',
    published: '2026-06-29',
  },
  {
    name: 'IoT',
    tagline: '物联网技术文档中心',
    description:
      '围绕开源物联网平台、工业总线协议与工控工具链的实战技术文档站，持续沉淀可检索、可落地的一手资料。',
    url: 'https://hackertodo.com/iot/',
    github: '',
    tags: ['Vue3', 'Vite', '文档站', 'IoT'],
    status: '进行中',
    published: '2026-09-13',
  },
]

// 产品 / 开发原则（参考 t9t.io 的透明创业实验理念，结合个人风格）
export const principles = [
  { no: 1, title: '从我的问题出发', desc: '只做我自己在用的东西，先解决自己的痛点，再谈分享。' },
  { no: 2, title: '小而美', desc: '每个产品专注解决一个问题，不堆砌功能，保持简单可用。' },
  { no: 3, title: '完整交付', desc: '上线即有完整形态：能用、好看、部署稳定，而非半成品 Demo。' },
  { no: 4, title: '开放共建', desc: '代码开源，和用户的反馈一起把产品打磨得更好。' },
  { no: 5, title: '可持续', desc: '低维护成本，让产品活得久一点，而不是昙花一现。' },
  { no: 6, title: '持续记录', desc: '把开发过程、思路与踩坑公开，既是对自己的复盘，也给他人参考。' },
]

// 关于 / 联系方式
export const about = {
  name: 'DoublePoint',
  slogan: 'Build something we like and want.',
  bio: '独立开发者，喜欢把日常里的小麻烦做成顺手的小工具。这里汇总了我做过的产品与实验。',
  email: 'leolau100@gmail.com',
  github: 'https://github.com/leolau100',
  links: [
    { label: 'GitHub', url: 'https://github.com/leolau100' },
    { label: 'NiceWeChatFile', url: 'https://hackertodo.com/' },
    { label: 'Happy English', url: 'https://hackertodo.com/happy/' },
  ],
}

// 博客 / 动态
export const posts = [
  {
    date: '2026-08-21',
    title: '作品集导航站上线',
    excerpt: '把 NiceWeChatFile、Happy English 等产品汇总到一个入口，方便查阅与分享。',
  },
  {
    date: '2026-08-20',
    title: 'NiceWeChatFile 列表样式修复',
    excerpt: '修复 Markdown 无序/有序列表在微信里回退到默认 17px 的问题，内联字体样式已补全。',
  },
  {
    date: '2026-08-19',
    title: 'Happy English 持续迭代',
    excerpt: '英语学习应用保持每周小步快跑，优化练习与复习体验。',
  },
]
