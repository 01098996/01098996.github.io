# 面向Google编程 · AI 日报

保留原有 Hexo 静态博客和历史日报。在 `/daily/` 按北京时间日期汇总公开 AI 信息，每小时采集进入编辑草稿；未经核实且没有完整原创正文的内容不新增发布。已发表的简讯卡片保留 URL，并明确标注待补充正文。

## 云端每小时查新

复用已有 `.github/workflows/daily-topup.yml`（Actions 名称 **AI Hourly**），cron 为 `23 * * * *`：UTC 每小时 **:23**，北京时间同样每小时 **:23**。保留 `.github/workflows/daily.yml` 的每日任务，UTC **01:07** / 北京时间 **09:07**，并在 master push 后验证、采集和部署。调度与运行都在 GitHub，电脑关机后仍可执行；没有本机或额外 ChatGPT 定时器。

GitHub Actions 的定时任务可能延迟或被丢弃，不保证准点。公共仓库长期无活动时 GitHub 也可能暂停定时工作流。可在 Actions → AI Hourly → Run workflow 手动执行。Pages 的 Source 应沿用 GitHub Actions；不要改域名或密钥。

## 采集与内容边界

- 使用 11 个已有公开 RSS/Atom 源（Simon Willison、Hugging Face、OpenAI、Hacker News、量子位、Weaviate、Google Research、Microsoft Research、Armin Ronacher、Hamel Husain、Latent Space），加 GitHub 公开新项目搜索。每个来源每轮一次请求，无伪装浏览器、反爬重试、付费墙访问或全文抓取。
- 近 7 天且有明确日期的条目才参与筛选。优先模型、工具、Agent、编程、评测和应用，允许具体产品发布；拒绝融资、收购、招聘和泛泛的 AI 讨论。没有足够的标题/摘要证据就跳过。
- 每小时最多追加 **2** 条，每日任务最多追加 **4** 条，当日合计最多 **12** 条。到达上限后仍每小时检索但不继续追加；无合适新内容就保持原发布数据，不凑数、不制造空日报。
- **发布门禁已关闭规则卡片自动发布：RSS 结果仅存于 `scripts/discovery/` 草稿。正文由编辑阶段核实和撰写，达标后才允许发布。**
- **不调用模型 API，不使用付费服务，不新增凭据。** 用来源中的名称、主题与日期，配合预设中文分析和验证问题生成短解读。它是透明的主题导读，不是逐篇深度摘要或全文翻译；英文原标题保留，中文标题加主题说明。历史译文和图片保留，新条目不搬运正文或图片。
- 页面区分「来源事实」和「短解读（分析）」。日期来自公开 Feed 的发布时间或更新时间；GitHub 项目使用创建时间，明确不当作产品发布日期。事件发生时间没有独立确认。不会编造博主亲测经历或个人观点。
- 来源内容只作为数据。原文 URL 由代码生成并经过协议校验，HTML 输出转义。模型/工具关键词只是主题线索，不能当作性能承诺。RSS 可能错标时间、延迟或遗漏消息；全网新闻覆盖和事件级跨站语义去重没有保证。

## 预算、去重与发布一致性

`scripts/briefs.py` 将联网采集放在独立进程，**150 秒硬预算**。每完成一个来源就写原子检查点，超时回收已有有效结果。单源失败记日志；全部失败或没有有效检查点则失败退出，保留历史和当天旧数据。采集步骤另有 4 分钟限额，整个工作流保留 20 分钟限额，为提交和部署留时间。

历史 `daily/data/*.json` 是去重依据，URL 去除追踪参数、片段和尾斜线后跨日期去重，同时过滤重复标题。当天只追加，不覆盖已有文章或改变旧序号。JSON 原子写入；无新增时 JSON 保持原字节。失败的构建不会覆盖线上网站。

两个已有工作流继续共享 `ai-daily-pages` 并发组，`cancel-in-progress: false`。取得锁后 checkout 当前 master，读取最新去重历史。提交同时包括 `daily/` 和 `sitemap.xml`；push 仅快进，遇到外部并发修改会停止，下一轮从新历史重试，不强推或覆盖。GitHub 并发组最多保留一个 pending run，排队任务仍可能被后来的任务替换。

生产渲染只修改当天文章和全局索引，不重写历史文章。打包排除脚本、私有目录和原始 JSON；Pages 工件中的 `/daily/deployment.json` 记录实际 source commit 与 Actions run URL，便于核对公开部署。Workflow 使用既有权限，保留已有密钥和变量，新的采集步骤只读 `DAILY_SITE_URL`。

## 手动运行

```sh
python3 -u scripts/daily.py --hourly
python3 -u scripts/daily.py --force
python3 -u scripts/daily.py --hourly --candidates /tmp/ai-candidates.json
```

`--hourly` 追加最多两条；`--force` 追加最多四条，也不会替换已发表文章；候选模式不发布。`--render-only` 显式全量重建历史页面，请仅在确实需要重建时使用。

## 微信推送（发布后自动）

旧代码保留了 Server酱/PushPlus 集成，但新的定时发布流程不发送微信通知，也不读取推送凭据。以下为已有服务的配置参考：

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
