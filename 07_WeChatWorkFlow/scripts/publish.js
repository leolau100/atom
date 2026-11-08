#!/usr/bin/env node

/**
 * scripts/publish.js
 *
 * 将排版后的文章 HTML 和封面图推送至微信公众号草稿箱。
 *
 * 用法：
 *   node scripts/publish.js [--article <article_path>] [--cover <cover_path>]
 *
 * 参数：
 *   --article    可选，文章 HTML 文件路径，默认为 output/article.html
 *   --cover      可选，封面图文件路径，默认为 output/cover.png
 *
 * 环境配置（.env 文件）：
 *   WECHAT_APP_ID      微信公众号 AppID
 *   WECHAT_APP_SECRET  微信公众号 AppSecret
 */

'use strict';

const fs   = require('fs');
const path = require('path');

// ── 依赖检查 ──────────────────────────────────────────────────────────────────
let axios, dotenv;

try {
  dotenv = require('dotenv');
} catch (e) {
  die('缺少依赖 dotenv', '请在项目根目录执行：npm install', 1);
}

try {
  axios = require('axios');
} catch (e) {
  die('缺少依赖 axios', '请在项目根目录执行：npm install', 1);
}

// ── 常量 ──────────────────────────────────────────────────────────────────────
const PROJECT_ROOT    = path.resolve(__dirname, '..');
const DEFAULT_ARTICLE = path.join(PROJECT_ROOT, 'output', 'article.html');
const DEFAULT_COVER   = path.join(PROJECT_ROOT, 'output', 'cover.png');
const WECHAT_API_BASE = 'https://api.weixin.qq.com/cgi-bin';

// ── 工具函数 ──────────────────────────────────────────────────────────────────

/**
 * 向 stderr 输出错误信息并以非零状态码退出。
 * 本地文件不做任何删除操作。
 */
function die(reason, advice, code = 1) {
  process.stderr.write(`\n❌ 错误：${reason}\n`);
  if (advice) {
    process.stderr.write(`💡 建议：${advice}\n`);
  }
  process.stderr.write('\n');
  process.exit(code);
}

/** 解析命令行参数 */
function parseArgs() {
  const args = process.argv.slice(2);

  if (args[0] === '--help' || args[0] === '-h') {
    process.stdout.write(
      '\n用法：node scripts/publish.js [--article <path>] [--cover <path>]\n\n' +
      '参数：\n' +
      '  --article    可选，文章 HTML 文件路径（默认：output/article.html）\n' +
      '  --cover      可选，封面图文件路径（默认：output/cover.png）\n\n' +
      '示例：\n' +
      '  node scripts/publish.js\n' +
      '  node scripts/publish.js --article output/article.html --cover output/cover.png\n\n'
    );
    process.exit(0);
  }

  let articlePath = DEFAULT_ARTICLE;
  let coverPath   = DEFAULT_COVER;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--article') {
      if (!args[i + 1]) die('--article 选项需要提供文件路径', '示例：--article output/article.html');
      articlePath = path.resolve(args[++i]);
    } else if (args[i] === '--cover') {
      if (!args[i + 1]) die('--cover 选项需要提供文件路径', '示例：--cover output/cover.png');
      coverPath = path.resolve(args[++i]);
    } else {
      die(`未知选项：${args[i]}`, '使用 --help 查看完整用法');
    }
  }

  return { articlePath, coverPath };
}

/** 读取文件，不存在时调用 die() */
function readFileSafe(filePath, label) {
  if (!fs.existsSync(filePath)) {
    die(
      `${label}文件不存在：${filePath}`,
      `请先执行排版和封面生成脚本，或通过 --article / --cover 参数指定正确路径`
    );
  }
  try {
    return fs.readFileSync(filePath);
  } catch (err) {
    die(`读取${label}文件失败：${err.message}`, `请检查文件读取权限：${filePath}`);
  }
}

/** 加载环境变量并校验必要字段 */
function loadEnvConfig() {
  const envPath = path.join(PROJECT_ROOT, '.env');
  if (fs.existsSync(envPath)) {
    dotenv.config({ path: envPath });
  } else {
    dotenv.config();
  }

  const appId     = process.env.WECHAT_APP_ID;
  const appSecret = process.env.WECHAT_APP_SECRET;

  if (!appId || appId === 'your_wechat_app_id_here') {
    die(
      '未配置 WECHAT_APP_ID',
      '请复制 .env.example 为 .env，并填入真实的微信公众号 AppID 和 AppSecret'
    );
  }
  if (!appSecret || appSecret === 'your_wechat_app_secret_here') {
    die(
      '未配置 WECHAT_APP_SECRET',
      '请复制 .env.example 为 .env，并填入真实的微信公众号 AppID 和 AppSecret'
    );
  }

  return { appId, appSecret };
}

/** 处理微信 API 错误码 */
function handleWechatError(res, context) {
  if (res.data && res.data.errcode && res.data.errcode !== 0) {
    const { errcode, errmsg } = res.data;
    let advice = '请查阅微信公众平台文档：https://developers.weixin.qq.com/doc/offiaccount/';

    if (errcode === 40001 || errcode === 42001) {
      advice = 'Access Token 已过期，请重新运行脚本重新获取';
    } else if (errcode === 45009) {
      advice = '接口调用次数已达上限，请明日再试';
    } else if (errcode === 40003) {
      advice = '无效的 OpenID，请检查配置';
    }

    die(`微信 API 错误（${context}）：[${errcode}] ${errmsg}`, advice);
  }
}

// ── 微信 API 调用 ─────────────────────────────────────────────────────────────

/** 获取微信 Access Token */
async function getAccessToken(appId, appSecret) {
  process.stdout.write('⏳ 正在获取 Access Token...\n');

  let res;
  try {
    res = await axios.get(`${WECHAT_API_BASE}/token`, {
      params: { grant_type: 'client_credential', appid: appId, secret: appSecret },
      timeout: 10000,
    });
  } catch (err) {
    const reason = err.response
      ? `HTTP ${err.response.status}：${err.response.statusText}`
      : `网络错误：${err.message}`;
    die(`获取 Access Token 失败（${reason}）`, '请检查网络连接，或确认 AppID / AppSecret 是否正确');
  }

  handleWechatError(res, '获取 Access Token');

  const { access_token, expires_in } = res.data;
  process.stdout.write(`✅ Access Token 获取成功（有效期 ${expires_in}s）\n`);
  return access_token;
}

/** 上传封面图至永久素材库，返回 media_id */
async function uploadCoverImage(accessToken, coverPath) {
  process.stdout.write('⏳ 正在上传封面图至素材库...\n');

  const coverBuffer = readFileSafe(coverPath, '封面图');
  const ext         = path.extname(coverPath).toLowerCase().replace('.', '') || 'png';
  const mimeMap     = { png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg', gif: 'image/gif' };
  const mimeType    = mimeMap[ext] || 'image/png';

  // 构造 multipart/form-data（手动拼接，避免引入额外依赖）
  const boundary = `----WeChatBoundary${Date.now()}`;
  const filename  = path.basename(coverPath);

  const head = Buffer.from(
    `--${boundary}\r\n` +
    `Content-Disposition: form-data; name="media"; filename="${filename}"\r\n` +
    `Content-Type: ${mimeType}\r\n\r\n`
  );
  const tail = Buffer.from(`\r\n--${boundary}--\r\n`);
  const body = Buffer.concat([head, coverBuffer, tail]);

  let res;
  try {
    res = await axios.post(
      `${WECHAT_API_BASE}/material/add_material`,
      body,
      {
        params: { access_token: accessToken, type: 'image' },
        headers: {
          'Content-Type': `multipart/form-data; boundary=${boundary}`,
          'Content-Length': body.length,
        },
        timeout: 30000,
      }
    );
  } catch (err) {
    const reason = err.response
      ? `HTTP ${err.response.status}：${err.response.statusText}`
      : `网络错误：${err.message}`;
    die(`上传封面图失败（${reason}）`, '请检查网络连接，本地封面文件已保留');
  }

  handleWechatError(res, '上传封面图');

  const { media_id, url } = res.data;
  process.stdout.write(`✅ 封面图上传成功（media_id: ${media_id}）\n`);
  if (url) process.stdout.write(`   素材 URL：${url}\n`);
  return media_id;
}

/** 从 HTML 中提取 <title> 标签内容作为文章标题 */
function extractTitle(html) {
  const match = html.toString('utf8').match(/<title[^>]*>([^<]+)<\/title>/i);
  return match ? match[1].trim() : '未命名文章';
}

/** 推送文章至草稿箱，返回 media_id */
async function addDraft(accessToken, articleHtml, thumbMediaId) {
  process.stdout.write('⏳ 正在推送文章至草稿箱...\n');

  const htmlStr = articleHtml.toString('utf8');
  const title   = extractTitle(articleHtml);

  const payload = {
    articles: [
      {
        title,
        thumb_media_id: thumbMediaId,
        author: '',
        digest: '',
        show_cover_pic: 1,
        content: htmlStr,
        content_source_url: '',
        need_open_comment: 0,
        only_fans_can_comment: 0,
      },
    ],
  };

  let res;
  try {
    res = await axios.post(
      `${WECHAT_API_BASE}/draft/add`,
      payload,
      {
        params: { access_token: accessToken },
        headers: { 'Content-Type': 'application/json; charset=UTF-8' },
        timeout: 15000,
      }
    );
  } catch (err) {
    const reason = err.response
      ? `HTTP ${err.response.status}：${err.response.statusText}`
      : `网络错误：${err.message}`;
    die(`推送草稿失败（${reason}）`, '请检查网络连接，本地文章和封面文件已保留');
  }

  handleWechatError(res, '推送草稿');

  const { media_id } = res.data;
  return media_id;
}

// ── 主流程 ────────────────────────────────────────────────────────────────────

async function main() {
  process.stdout.write('\n📤 微信公众号草稿箱推送工具\n');
  process.stdout.write('─'.repeat(40) + '\n');

  // 1. 解析命令行参数
  const { articlePath, coverPath } = parseArgs();

  // 2. 加载环境变量
  const { appId, appSecret } = loadEnvConfig();

  // 3. 预检文件（在发起任何网络请求之前确认文件存在）
  const articleHtml = readFileSafe(articlePath, '文章 HTML');
  // 封面存在性预检（内容在上传步骤中读取）
  if (!fs.existsSync(coverPath)) {
    die(
      `封面图文件不存在：${coverPath}`,
      `请先执行 node scripts/cover.js 生成封面图，或通过 --cover 参数指定正确路径`
    );
  }

  process.stdout.write(`   文章：${path.relative(PROJECT_ROOT, articlePath)}\n`);
  process.stdout.write(`   封面：${path.relative(PROJECT_ROOT, coverPath)}\n\n`);

  // 4. 获取 Access Token
  const accessToken = await getAccessToken(appId, appSecret);

  // 5. 上传封面图
  const thumbMediaId = await uploadCoverImage(accessToken, coverPath);

  // 6. 推送文章至草稿箱
  const draftMediaId = await addDraft(accessToken, articleHtml, thumbMediaId);

  // 7. 输出成功信息
  process.stdout.write('\n' + '─'.repeat(40) + '\n');
  process.stdout.write('🎉 文章已成功推送至微信公众号草稿箱！\n');
  process.stdout.write(`   草稿 media_id：${draftMediaId}\n`);
  process.stdout.write('   请前往微信公众平台 → 草稿箱 查看文章\n');
  process.stdout.write('   https://mp.weixin.qq.com\n\n');
}

main().catch((err) => {
  die(`未预期的错误：${err.message}`, '请检查运行环境或查阅错误详情');
});
