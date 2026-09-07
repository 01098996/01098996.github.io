# 面向Google编程 · AI 日报

原有 Hexo 静态博客保留，新增 `/daily/` 专栏、按日期固定链接、归档和 Atom 订阅。

## 每日发布

`.github/workflows/daily.yml` 每天北京时间 **09:07** 抓取文章、去重、生成页面并通过 GitHub Pages 发布。GitHub 定时执行可能延迟，不保证准点。首次部署须在 **Settings → Pages → Source** 选择 **GitHub Actions**。也可在 Actions → AI Daily → Run workflow 手动运行。

- 默认检查 Simon Willison、Hugging Face、OpenAI 的 RSS/Atom，筛选近 7 天、尚未推荐过的文章。
- 每期最多 5 篇，每个来源最多 2 篇；无新增内容时明确显示空状态。
- 任一来源失败会显示覆盖不完整提示；全部失败则终止更新并保留旧日报。
- 当天重跑不覆盖已发布内容。历史 JSON 是去重依据，勿删除。
- 候选正文只在内存处理，公共仓库仅保存中文导读或极短原文节选，不存全文。
- 发布包排除脚本、数据源 JSON、凭证和开发目录。

### 中文导读（可选配置）

首期中文导读已核对来源。后续自动生成需要配置兼容 Chat Completions 的模型接口：

| 配置位置 | 名称 | 内容 |
| --- | --- | --- |
| Actions Secret | `DAILY_LLM_API_KEY` | 模型 API 密钥 |
| Actions Variable | `DAILY_LLM_ENDPOINT` | 完整 HTTPS chat/completions 接口地址 |
| Actions Variable | `DAILY_LLM_MODEL` | 服务支持的模型名称 |
| Actions Variable | `DAILY_SITE_URL` | 网站根地址，无末尾斜线 |

未配置或调用失败时，仍抓取文章、发布链接和短节选，并明确标注中文导读未生成。不会把标题猜测包装成全文总结。模型只接收公开文章标题和片段，页面对模型返回内容统一转义。

## 独立微信连接器

`scripts/weixin_bridge.py` 参考腾讯维护的 iLink 接入源码，**不安装或运行 OpenClaw**。仅实现扫码授权、接收本人指令和发送日报链接。登录凭证和会话游标必须存于网站仓库之外，文件权限为 0600。

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
- 已发送日期持久化保存；同一期不会自动重复发送。
- 发送结果未知时留下 pending 标记并停止后续发送。先在微信确认有无送达，再由管理员核对并修复状态，避免盲目重试。
- `watch` 需要一个持续运行、联网的进程，可放在常开电脑或自己的服务器。GitHub Pages 只承载网页，不运行这个进程。
- 上游会话、context token 和账号资格受微信服务控制。长期主动推送需要真实账号验证，不能由一次成功发送推断永久有效。
- 遇到扫码验证或账号状态限制需要本人完成，程序不绕过验证。

## 验证与本地预览

```sh
python3 -m unittest discover -s scripts -p 'test_*.py'
python3 scripts/daily.py --render-only
python3 scripts/package_site.py
python3 -m http.server --directory _site
```

发布仅依赖 Python；模型密钥和微信凭证不写入 HTML、Git 或浏览器代码。后续如果重新用 Hexo 全量部署，请先把日报入口及专栏目录纳入 Hexo 源项目，以免生成产物覆盖这个专栏。
