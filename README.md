# 面向Google编程 · AI 日报

原有 Hexo 静态博客保留，新增 `/daily/` 专栏：每天精选文章，**逐篇落盘为独立页面**，英文文章附带**全文中文翻译**，文末保留**原文链接**，并支持推送到个人微信。不安装、不依赖 OpenClaw。

## 每日发布

`.github/workflows/daily.yml` 每天北京时间 **09:07** 抓取文章、抓取全文、翻译、生成页面并通过 GitHub Pages 发布。GitHub 定时执行可能延迟，不保证准点。首次部署须在 **Settings → Pages → Source** 选择 **GitHub Actions**。也可在 Actions → AI Daily → Run workflow 手动运行。

- 来源：Simon Willison、Hugging Face、OpenAI 的 RSS/Atom，外加 r/LocalLLaMA、r/AI_Agents、r/ClaudeAI、r/LLMDevs、r/PromptEngineering、r/MachineLearning 六个 Reddit 社区（RSS 抓取，串行限速）。
- 每期最多 **8** 篇，每个来源最多 2 篇；无新增内容时明确显示空状态。
- 任一来源失败会显示覆盖不完整提示；全部失败则终止更新并保留旧日报。
- 当天重跑不覆盖已发布内容（本地重建可用 `daily.py --force` 重新生成当天）。历史 JSON 是去重依据，勿删除。

## 每篇文章一个独立页面

- 每篇精选生成 `daily/<日期>/<序号>-<哈希>/index.html`，本期页面中的标题直接链到本地页面。
- 抓取正文只提取 `article`/`main` 区域，剔除脚本、表单和评论，最长 20000 字符。
- 英文文章经过**两道工序**：先逐篇忠实翻译为简体中文（代码、命令、专有名词保留原样），再按「数字生命卡兹克」文风做润色 pass——消灭翻译腔和 AI 味（禁用套话、翻译腔标点，长短句节奏、聊天感），但事实、结构、代码严格不动。超过 20000 字符的只翻译节选并在页面标注；中文文章保留原文。
- 原文链接由代码以固定格式拼装在文末，不经过模型；正文中模型不输出任何链接。
- 翻译失败或未配置模型时，页面回退为原文节选 + 明确提示，并始终保留原文链接。
- 译文仅供学习交流，页面标注版权归原作者所有、以原文为准。

### 翻译与导读（必须配置才能生成译文）

| 配置位置 | 名称 | 内容 |
| --- | --- | --- |
| Actions Secret | `DAILY_LLM_API_KEY` | 模型 API 密钥 |
| Actions Variable | `DAILY_LLM_ENDPOINT` | 完整 HTTPS chat/completions 接口地址（OpenAI 兼容） |
| Actions Variable | `DAILY_LLM_MODEL` | 服务支持的模型名称 |
| Actions Variable | `DAILY_SITE_URL` | 网站根地址，无末尾斜线（如 `https://z-xj.com`） |

## 微信推送（发布后自动）

日报发布成功后，会把本期标题列表和链接推送到你的个人微信。支持两个服务，任选其一：

| 服务 | 获取方式 | 配置 |
| --- | --- | --- |
| [Server酱](https://sct.ftqq.com/) | 微信扫码登录 → 复制 SendKey（`SCT` 开头） | Actions Secret `WECHAT_PUSH_KEY` |
| [PushPlus](https://www.pushplus.plus/) | 微信扫码登录 → 复制 token | Actions Secret `WECHAT_PUSH_KEY` |

推送内容为「本期标题 + 每篇译文页直达链接 + 本期页面链接」，点击后在网页上阅读。推送失败不影响发布。

## 可选：独立微信连接器（扫码机器人方案）

`scripts/weixin_bridge.py` 参考腾讯维护的 iLink 接入源码实现，仅支持扫码授权、接收本人指令和发送日报链接。登录凭证和会话游标必须存于网站仓库之外，文件权限为 0600。

```sh
python3 -m venv /path/to/private-runtime
/path/to/private-runtime/bin/pip install -r scripts/requirements.txt
/path/to/private-runtime/bin/python scripts/weixin_bridge.py login-start --state /private/path/weixin.json --qr /private/path/login.png
/path/to/private-runtime/bin/python scripts/weixin_bridge.py login-wait --state /private/path/weixin.json
# 手机扫码确认后，给新出现的微信机器人发送“日报”，建立会话上下文。
/path/to/private-runtime/bin/python scripts/weixin_bridge.py watch --state /private/path/weixin.json --site https://YOUR-SITE
```

- 微信中发送 `日报` 或 `订阅日报` 恢复订阅；`停止日报` 暂停。
- 只接受扫码人的消息，不收集其他聊天，不执行自然语言命令。
- `watch` 需要一个持续运行、联网的进程（常开电脑或自己的服务器）；上游会话与账号资格受微信服务控制，遇到扫码验证需本人完成。

> 日常推荐使用上面的 Server酱/PushPlus 推送（零维护、不需要常开电脑）；扫码机器人方案仅作为进阶备选。

## 验证与本地预览

```sh
python3 -m unittest discover -s scripts -p 'test_*.py'
python3 scripts/daily.py --render-only
python3 scripts/package_site.py
python3 -m http.server --directory _site
```

发布仅依赖 Python；模型密钥和推送密钥不写入 HTML、Git 或浏览器代码。后续如果重新用 Hexo 全量部署，请先把日报入口及专栏目录纳入 Hexo 源项目，以免生成产物覆盖这个专栏。
