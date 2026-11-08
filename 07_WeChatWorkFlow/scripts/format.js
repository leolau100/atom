#!/usr/bin/env node

/**
 * scripts/format.js
 *
 * 将 Markdown 文章应用至 HTML 排版模板，生成符合微信公众号格式的 HTML 文件。
 *
 * 用法：
 *   node scripts/format.js <article_path> [--output <output_path>]
 *
 * 参数：
 *   article_path   必填，Markdown 文件路径
 *   --output       可选，输出 HTML 文件路径，默认为 output/article.html
 */

'use strict';

const fs = require('fs');
const path = require('path');

// ── 依赖检查 ──────────────────────────────────────────────────────────────────
let marked;
try {
  marked = require('marked');
} catch (e) {
  die(
    '缺少依赖 marked',
    '请在项目根目录执行：npm install',
    1
  );
}

// ── 常量 ──────────────────────────────────────────────────────────────────────
const PROJECT_ROOT = path.resolve(__dirname, '..');
const DEFAULT_TEMPLATE = path.join(PROJECT_ROOT, 'templates', 'format-template.html');
const DEFAULT_OUTPUT   = path.join(PROJECT_ROOT, 'output', 'article.html');

// ── 工具函数 ──────────────────────────────────────────────────────────────────

/**
 * 向 stderr 输出含错误原因和建议操作的结构化错误信息，并以非零状态码退出。
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
 * @returns {{ articlePath: string, outputPath: string }}
 */
function parseArgs() {
  const args = process.argv.slice(2);

  if (args.length === 0 || args[0] === '--help' || args[0] === '-h') {
    process.stdout.write(
      '\n用法：node scripts/format.js <article_path> [--output <output_path>]\n\n' +
      '参数：\n' +
      '  article_path   必填，Markdown 文件路径\n' +
      '  --output       可选，输出 HTML 文件路径（默认：output/article.html）\n\n' +
      '示例：\n' +
      '  node scripts/format.js articles/article.md\n' +
      '  node scripts/format.js articles/article.md --output output/my-article.html\n\n'
    );
    process.exit(0);
  }

  let articlePath = null;
  let outputPath  = DEFAULT_OUTPUT;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--output' || args[i] === '-o') {
      if (!args[i + 1]) {
        die('--output 选项需要提供输出路径', '示例：--output output/my-article.html');
      }
      outputPath = path.resolve(args[i + 1]);
      i++; // 跳过下一个 token
    } else if (!args[i].startsWith('-')) {
      articlePath = path.resolve(args[i]);
    } else {
      die(`未知选项：${args[i]}`, '使用 --help 查看完整用法');
    }
  }

  if (!articlePath) {
    die('缺少必填参数：article_path', '示例：node scripts/format.js articles/article.md');
  }

  return { articlePath, outputPath };
}

/**
 * 从 Markdown 内容中提取第一个一级标题（# Title）作为文章标题。
 * 若无一级标题，返回空字符串。
 *
 * @param {string} markdown
 * @returns {string}
 */
function extractTitle(markdown) {
  const match = markdown.match(/^#\s+(.+)$/m);
  return match ? match[1].trim() : '';
}

/**
 * 读取文件内容。若文件不存在或无读权限则调用 die() 退出。
 *
 * @param {string} filePath
 * @param {string} label    用于错误提示的文件描述（如"Markdown 文章"）
 * @returns {string}
 */
function readFileSafe(filePath, label) {
  if (!fs.existsSync(filePath)) {
    die(
      `${label}文件不存在：${filePath}`,
      `请确认文件路径正确，或使用 articles/ 目录下已存在的 Markdown 文件`
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
 * 将模板字符串中的占位符（{{key}}）替换为对应值。
 * 若模板中缺少必要占位符，抛出错误。
 *
 * @param {string} template
 * @param {{ title: string, content: string, author: string }} vars
 * @returns {string}
 */
function applyTemplate(template, vars) {
  const required = ['title', 'content'];
  for (const key of required) {
    if (!template.includes(`{{${key}}}`)) {
      throw new Error(`模板缺少占位符：{{${key}}}，请检查 templates/format-template.html`);
    }
  }

  return template
    .replace(/\{\{title\}\}/g,   vars.title   || '（无标题）')
    .replace(/\{\{content\}\}/g, vars.content  || '')
    .replace(/\{\{author\}\}/g,  vars.author   || '');
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

// ── 主流程 ────────────────────────────────────────────────────────────────────

function main() {
  // 1. 解析命令行参数
  const { articlePath, outputPath } = parseArgs();

  // 2. 读取 Markdown 文件
  const markdown = readFileSafe(articlePath, 'Markdown 文章');

  // 3. 读取排版模板
  const template = readFileSafe(DEFAULT_TEMPLATE, 'HTML 排版模板');

  // 4. 解析 Markdown → HTML
  let contentHtml;
  try {
    // marked v5+ 使用 marked.parse()；v4 及以下直接调用 marked()
    const parseFn = typeof marked.parse === 'function' ? marked.parse : marked;
    contentHtml = parseFn(markdown, { mangle: false, headerIds: false });
  } catch (err) {
    die(
      `Markdown 解析失败：${err.message}`,
      `请确认文件内容为合法的 Markdown 格式`
    );
  }

  // 5. 提取标题
  const title = extractTitle(markdown);

  // 6. 注入模板占位符
  let html;
  try {
    html = applyTemplate(template, {
      title,
      content: contentHtml,
      author: '',   // 可在后续版本通过 --author 参数扩展
    });
  } catch (err) {
    die(
      `模板解析失败：${err.message}`,
      `请检查 templates/format-template.html 是否包含 {{title}}、{{content}}、{{author}} 占位符`
    );
  }

  // 7. 确保输出目录存在
  ensureOutputDir(outputPath);

  // 8. 写入输出文件
  try {
    fs.writeFileSync(outputPath, html, 'utf8');
  } catch (err) {
    die(
      `写入输出文件失败：${err.message}`,
      `请检查路径 ${outputPath} 的写入权限`
    );
  }

  // 9. 输出成功信息
  const relOutput = path.relative(process.cwd(), outputPath);
  const relInput  = path.relative(process.cwd(), articlePath);
  process.stdout.write(`\n✅ 排版完成\n`);
  process.stdout.write(`   输入：${relInput}\n`);
  process.stdout.write(`   输出：${relOutput}\n\n`);
}

main();
