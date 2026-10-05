# 面向Google编程 · AI 日报

保留原有 Hexo 静态博客和历史日报。在 `/daily/` 按北京时间日期汇总公开 AI 信息，每小时采集进入编辑草稿；未经核实且没有完整原创正文的内容不新增发布。已发表的简讯卡片保留 URL，并明确标注待补充正文。

## 云端每小时查新

复用已有 `.github/workflows/daily-topup.yml`（Actions 名称 **AI Hourly**），cron 为 `23 * * * *`：UTC 每小时 **:23**，北京时间同样每小时 **:23**。保留 `.github/workflows/daily.yml` 的每日任务，UTC **01:07** / 北京时间 **09:07**。GitHub cron 只负责采集草稿；master push 后只验证、渲染已批准正文并部署，不进行 RSS 采集。

**dot 云端每小时编辑任务已建立并启用**，负责阅读公开原文、核对事实和日期、撰写原创正文，并按下方契约更新编辑收件箱；提交后复用现有 Actions 发布。采集、编辑和部署均在云端运行，电脑关机后仍可执行。**首次自然定时触发尚未验证**，不能将手动运行成功当作自然触发已验证。

GitHub Actions 的定时任务可能延迟或被丢弃，不保证准点。公共仓库长期无活动时 GitHub 也可能暂停定时工作流。可在 Actions → AI Hourly → Run workflow 手动执行。Pages 的 Source 应沿用 GitHub Actions；不要改域名或密钥。

## 采集与内容边界

- 使用 11 个已有公开 RSS/Atom 源（Simon Willison、Hugging Face、OpenAI、Hacker News、量子位、Weaviate、Google Research、Microsoft Research、Armin Ronacher、Hamel Husain、Latent Space），加 GitHub 公开新项目搜索。每个来源每轮一次请求，无伪装浏览器、反爬重试、付费墙访问或全文抓取。
- 近 7 天且有明确日期的条目才参与筛选。优先模型、工具、Agent、编程、评测和应用，允许具体产品发布；拒绝融资、收购、招聘和泛泛的 AI 讨论。没有足够的标题/摘要证据就跳过。
- 每小时最多新增 **2** 条候选、每日采集最多新增 **4** 条，草稿队列每日最多 **24** 条。正式文章当日最多 **12** 篇。无合适新内容或没有通过正文门禁的稿件时不新增发布。
- **发布门禁已关闭规则卡片自动发布：RSS 结果仅存于 `scripts/discovery/` 草稿。正文由编辑阶段核实和撰写，达标后才允许发布。**
- **不调用模型 API，不使用付费服务，不新增凭据。** 采集器用名称、主题与日期形成编辑候选，预设文字只作为草稿线索，不再公开新发。正式正文必须经编辑任务阅读全文、核对主要事实和日期后原创撰写。历史译文和图片保留，新条目不搬运正文或图片。
- 页面区分「来源事实」和「短解读（分析）」。日期来自公开 Feed 的发布时间或更新时间；GitHub 项目使用创建时间，明确不当作产品发布日期。事件发生时间没有独立确认。不会编造博主亲测经历或个人观点。
- 来源内容只作为数据。原文 URL 由代码生成并经过协议校验，HTML 输出转义。模型/工具关键词只是主题线索，不能当作性能承诺。RSS 可能错标时间、延迟或遗漏消息；全网新闻覆盖和事件级跨站语义去重没有保证。

## 预算、去重与发布一致性

`scripts/briefs.py` 将联网采集放在独立进程，**150 秒硬预算**。每完成一个来源就写原子检查点，超时回收已有有效结果。单源失败记日志；全部失败或没有有效检查点则失败退出，保留历史和当天旧数据。采集步骤另有 4 分钟限额，整个工作流保留 20 分钟限额，为提交和部署留时间。

历史 `daily/data/*.json` 是去重依据，URL 去除追踪参数、片段和尾斜线后跨日期去重，同时过滤重复标题。当天只追加，不覆盖已有文章或改变旧序号。JSON 原子写入；无新增时 JSON 保持原字节。失败的构建不会覆盖线上网站。

两个已有工作流继续共享 `ai-daily-pages` 并发组，`cancel-in-progress: false`。取得锁后 checkout 当前 master，读取最新去重历史。提交同时包括 `daily/` 和 `sitemap.xml`；push 仅快进，遇到外部并发修改会停止，下一轮从新历史重试，不强推或覆盖。GitHub 并发组最多保留一个 pending run，排队任务仍可能被后来的任务替换。

生产渲染只修改当天文章和全局索引，不重写历史文章。打包排除脚本、私有目录和原始 JSON；Pages 工件中的 `/daily/deployment.json` 记录实际 source commit 与 Actions run URL，便于核对公开部署。Workflow 使用既有权限，保留已有密钥和变量，新的采集步骤只读 `DAILY_SITE_URL`。

## 编辑任务的单文件写入契约（version 1）

编辑任务唯一写入路径：**`scripts/editorial-inbox.json`**。它不修改定时工作流、采集草稿或 `daily/data`，也不调用站外模型 API。可以通过已有 GitHub create/update_file 提交 UTF-8 JSON；更新时使用刚读到的 content SHA，遇到并发冲突重新读取，不强制覆盖。

顶层为 `{"version":1,"articles":[...]}`。每次保留待处理的少量文章或追加本轮一篇。来源 URL 是幂等身份；已发布且正文相同的输入不会再次生成文章。已处理行可从收件箱移除，已发文章不受影响。

每篇字段：

| 字段 | 要求 |
| --- | --- |
| `approved` | 编辑核对完成后才设为 `true`；未完成保持 `false` |
| `source_url`, `source_title` | 主来源的完整 HTTPS 原文 URL 与原题 |
| `source_published_at` | 从原文/可信订阅核对的 ISO 时间，含时区；不能用抓取时间代替 |
| `publication_date` | 本期收录日期 `YYYY-MM-DD`，按北京时间；不等于来源发布日期 |
| `title_zh`, `summary`, `category`, `tags` | 中文标题、简短导语、分类与标签数组，保留事实归属 |
| `body_markdown` | 800–6000 字符、至少 600 个中文字；正常目标约 800–1500 中文字，以内容密度决定 |
| `sources` | 至少一个主来源；每项含 `url`, `title`, `publisher`, `kind:"primary"`, `published_at`。文档没有发布日期则该项为 `null`；主来源日期必须与 `source_published_at` 完全相同 |
| `reviewed_at` | 本轮完成事实核对的 ISO 时间，含时区 |
| `authoring_note` | 说明公开资料整理、哪些是分析、例子是否假设、没有亲测的边界 |
| `update_existing` | 默认不覆盖已有 URL；修订既有文章须 `true`，且使用原本 `publication_date`，保留原 URL 和序号 |

正文需有五个 `##` 二级章节：**事实与来源、技术机制、例子与用途、限制与不确定性、开发者启示**，每节至少 60 字符有效文字。讲清具体事实、机制、一个用例以及限制，避免重复模板；不能拿长度凑数、抄全文或虚构个人亲测。关键事实应在原始来源中能定位，发布方的性能说法须归属发布方，推断单独说明；无合格内容就不设置批准。

**机器门禁检查结构，不会自动证明事实正确或文笔足够好。** 编辑阶段必须完成实质核对。无批准、短卡片、缺章节、占位文字、重复段落、未来日期、超过七天的主来源、无主来源或日期不一致，都只保留在收件箱，不发布、不覆盖旧文章。

编辑提交到 master 会触发现有 AI Daily push 流程的 `daily.py --publish-only`：校验收件箱 → 按原 URL 追加或明确修订 → 生成页面与全局索引 → 提交生成产物 → Pages 部署。采集 cron 只写 `scripts/discovery/`；发布者只读编辑收件箱，二者不会竞争编辑文件。公共 `/daily/deployment.json` 标明实际源码提交与运行 URL。须核对 CI、部署和公开正文后才算本轮完成。

已接入的 dot 云端每小时编辑任务使用现有公开检索与推理能力，读取本节契约、阅读全文并核对来源，再撰写原创正文。它唯一写入 `scripts/editorial-inbox.json`，无合格内容则跳过，提交后核对 CI、Pages 部署和公开文章。GitHub cron 继续只采集草稿，不自动发短卡片；编辑任务复用现有发布流程，不新增重复发布调度。**首次自然定时触发尚未验证。**

## 手动运行

```sh
python3 -u scripts/daily.py --hourly
python3 -u scripts/daily.py --force
python3 -u scripts/daily.py --publish-only
python3 -u scripts/daily.py --hourly --candidates /tmp/ai-candidates.json
```

`--hourly` 只新增最多两条草稿；`--force` 只新增最多四条草稿；候选模式不发布。`--render-only` 显式全量重建历史页面，请仅在确实需要重建时使用。

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
