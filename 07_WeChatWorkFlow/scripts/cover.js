#!/usr/bin/env node

/**
 * scripts/cover.js
 *
 * 基于封面模板和文章标题生成微信公众号封面图。
 *
 * 用法：
 *   node scripts/cover.js <title> [--output <output_path>]
 *
 * 参数：
 *   title          必填，文章标题（注入封面模板的 {{title}} 占位符）
 *   --output       可选，输出图片文件路径，默认为 output/cover.png
 */

'use strict';

const fs   = require('fs');
const path = require('path');

// ── 依赖检查 ──────────────────────────────────────────────────────────────────
let puppeteer;
try {
  puppeteer = require('puppeteer');
} catch (e) {
  die(
    '缺少依赖 puppeteer',
    '请在项目根目录执行：npm install',
    1
  );
}

// ── 常量 ──────────────────────────────────────────────────────────────────────
const PROJECT_ROOT    = path.resolve(__dirname, '..');
const DEFAULT_TEMPLATE = path.join(PROJECT_ROOT, 'templates', 'cover-template.html');
const DEFAULT_OUTPUT   = path.join(PROJECT_ROOT, 'output', 'cover.png');

// 封面图尺寸（与 cover-template.html 中的 CSS 保持一致）
const COVER_WIDTH  = 900;
const COVER_HEIGHT = 383;

// ── 工具函数 ──────────────────────────────────────────────────────────────────

/**
 * 向 stderr 输出错误信息并以非零状态码退出。
 *
 * @param {string} reason  错误原因（一句话说明）
 * @param {string} advice  建议操作（告知用户下一步怎么做）
 * @param {number} code    退出状态码，默认 1
 */
function die(reason, advice, code = 1) {
  process.stderr.write(`\n❌ 错误：${reason}\n`);
  if (advice) {
    process.stderr.write(`💡 建议：${advice}\n`);
  }
  process.stderr.write('\n');
  process.exit(code);
}

/**
 * 解析命令行参数。
 *
 * @returns {{ title: string, outputPath: string }}
 */
function parseArgs() {
  const args = process.argv.slice(2);

  if (args.length === 0 || args[0] === '--help' || args[0] === '-h') {
    process.stdout.write(
      '\n用法：node scripts/cover.js <title> [--output <output_path>]\n\n' +
      '参数：\n' +
      '  title          必填，文章标题\n' +
      '  --output       可选，输出图片文件路径（默认：output/cover.png）\n\n' +
      '示例：\n' +
      '  node scripts/cover.js "职场沟通的 5 个误区"\n' +
      '  node scripts/cover.js "职场沟通的 5 个误区" --output output/my-cover.png\n\n'
    );
    process.exit(0);
  }

  let title      = null;
  let outputPath = DEFAULT_OUTPUT;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--output' || args[i] === '-o') {
      if (!args[i + 1]) {
        die('--output 选项需要提供输出路径', '示例：--output output/my-cover.png');
      }
      outputPath = path.resolve(args[i + 1]);
      i++; // 跳过下一个 token
    } else if (!args[i].startsWith('-')) {
      title = args[i];
    } else {
      die(`未知选项：${args[i]}`, '使用 --help 查看完整用法');
    }
  }

  if (!title || title.trim() === '') {
    die('缺少必填参数：title', '示例：node scripts/cover.js "我的文章标题"');
  }

  return { title: title.trim(), outputPath };
}

/**
 * 读取文件内容。若文件不存在则调用 die() 退出。
 *
 * @param {string} filePath
 * @param {string} label    用于错误提示的文件描述
 * @returns {string}
 */
function readFileSafe(filePath, label) {
  if (!fs.existsSync(filePath)) {
    die(
      `${label}文件不存在：${filePath}`,
      `请确认 templates/cover-template.html 文件存在`
    );
  }

  try {
    return fs.readFileSync(filePath, 'utf8');
  } catch (err) {
    die(
      `读取${label}文件失败：${err.message}`,
      `请检查文件读取权限：${filePath}`
    );
  }
}

/**
 * 将模板字符串中的 {{title}} 占位符替换为实际标题。
 * 若模板缺少 {{title}} 占位符则抛出错误。
 *
 * @param {string} template
 * @param {string} title
 * @returns {string}
 */
function applyTemplate(template, title) {
  if (!template.includes('{{title}}')) {
    throw new Error('模板缺少占位符：{{title}}，请检查 templates/cover-template.html');
  }

  // 对标题进行 HTML 实体转义，防止注入破坏模板结构
  const safeTitle = title
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');

  return template.replace(/\{\{title\}\}/g, safeTitle);
}

/**
 * 确保输出目录存在，不存在时自动创建。
 *
 * @param {string} outputPath
 */
function ensureOutputDir(outputPath) {
  const dir = path.dirname(outputPath);
  try {
    fs.mkdirSync(dir, { recursive: true });
  } catch (err) {
    die(
      `无法创建输出目录：${dir}（${err.message}）`,
      `请检查目录写入权限`
    );
  }
}

/**
 * 查找可用的 Chrome/Chromium 可执行文件路径。
 * 优先使用 puppeteer 自带的 Chrome，回退到系统安装的 Chrome。
 *
 * @returns {string|undefined} Chrome 可执行文件路径，若不存在则返回 undefined
 */
function findChromePath() {
  const candidates = [
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    '/usr/bin/google-chrome',
    '/usr/bin/chromium-browser',
    '/usr/bin/chromium',
  ];

  for (const p of candidates) {
    if (fs.existsSync(p)) {
      return p;
    }
  }
  return undefined;
}

/**
 * 使用 puppeteer 将 HTML 字符串渲染为 PNG 图片并写入指定路径。
 *
 * @param {string} html        注入标题后的 HTML 内容
 * @param {string} outputPath  输出图片的绝对路径
 */
async function renderCover(html, outputPath) {
  let browser;
  try {
    const launchOptions = {
      headless: true,
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--font-render-hinting=none',
      ],
    };

    // 若 puppeteer 内置 Chrome 不存在，尝试使用系统 Chrome
    try {
      const executablePath = puppeteer.executablePath();
      if (!fs.existsSync(executablePath)) {
        const systemChrome = findChromePath();
        if (systemChrome) {
          launchOptions.executablePath = systemChrome;
        }
      }
    } catch (_) {
      const systemChrome = findChromePath();
      if (systemChrome) {
        launchOptions.executablePath = systemChrome;
      }
    }

    browser = await puppeteer.launch(launchOptions);

    const page = await browser.newPage();

    // 设置视窗大小与封面图一致，确保截图尺寸精确
    await page.setViewport({ width: COVER_WIDTH, height: COVER_HEIGHT, deviceScaleFactor: 2 });

    // 直接加载 HTML 字符串，设置 baseURL 为模板目录以解析相对路径资源
    const templateDir = path.dirname(DEFAULT_TEMPLATE);
    await page.setContent(html, {
      waitUntil: 'load',
      timeout: 15000,
      baseUrl: `file://${templateDir}/`,
    });

    // 截取整个页面（clip 限定为封面尺寸）
    await page.screenshot({
      path: outputPath,
      type: 'png',
      clip: { x: 0, y: 0, width: COVER_WIDTH, height: COVER_HEIGHT },
    });
  } catch (err) {
    die(
      `封面渲染失败：${err.message}`,
      `请确认 puppeteer 安装完整（npm install），并检查系统是否支持 headless Chrome`
    );
  } finally {
    if (browser) {
      await browser.close();
    }
  }
}

// ── 主流程 ────────────────────────────────────────────────────────────────────

async function main() {
  // 1. 解析命令行参数
  const { title, outputPath } = parseArgs();

  // 2. 读取封面模板
  const template = readFileSafe(DEFAULT_TEMPLATE, 'HTML 封面模板');

  // 3. 注入标题至模板
  let html;
  try {
    html = applyTemplate(template, title);
  } catch (err) {
    die(
      `模板处理失败：${err.message}`,
      `请检查 templates/cover-template.html 是否包含 {{title}} 占位符`
    );
  }

  // 4. 确保输出目录存在
  ensureOutputDir(outputPath);

  // 5. 使用 puppeteer 渲染封面图
  process.stdout.write(`\n⏳ 正在渲染封面图...\n`);
  await renderCover(html, outputPath);

  // 6. 输出成功信息
  const relOutput = path.relative(process.cwd(), outputPath);
  process.stdout.write(`✅ 封面生成完成\n`);
  process.stdout.write(`   标题：${title}\n`);
  process.stdout.write(`   输出：${relOutput}\n`);
  process.stdout.write(`   尺寸：${COVER_WIDTH}×${COVER_HEIGHT} px（deviceScaleFactor=2）\n\n`);
}

main().catch((err) => {
  die(
    `未预期的错误：${err.message}`,
    `请检查运行环境或联系开发者`
  );
});
