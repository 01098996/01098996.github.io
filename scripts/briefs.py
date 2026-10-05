"""Bounded, credential-free RSS discovery and Chinese editorial notes.

Feed text is evidence for classification, not public article body. No model, full
article scraping, images, payment, or notification is involved in this pipeline.
"""
import concurrent.futures
import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.parse
from pathlib import Path

import daily

SCAN_SECONDS = 150  # Hard process deadline, including a slow or trickling response.
PER_RUN = 2
SOURCES = [s for s in daily.SOURCES if s[0] in {
    'Simon Willison', 'Hugging Face', 'OpenAI', 'Hacker News', '量子位',
    'Weaviate', 'Google Research', 'Microsoft Research', 'Armin Ronacher',
    'Hamel Husain', 'Latent Space',
}]

# Each rule supplies a source-grounded theme, an explicit inference, and a
# concrete verification question. These are editorial templates, not measured
# outcomes or translations. Matching requires evidence in title/feed metadata.
RULES = [
    ('AI 编程实践', r'coding.agent|claude.code|\bcodex\b|vibe.cod|ai.assisted|代码生成|编程助手|编程智能体',
     '编程助手', '工具能否帮上忙，取决于它在现有项目里如何定位文件、执行检查并呈现改动。可以用一个小修复任务比较完成时间和人工复核量。',
     '来源是否给出了可复现的仓库、执行权限和验证步骤？'),
    ('Agent 开发', r'\bagents?\b|agentic|multi.agent|智能体|多智能体',
     '智能体工作流', '可执行的工作流比演示中的回答更值得观察。工具调用失败后的恢复、状态保存和人工介入点，会直接影响能否长期运行。',
     '任务中断后能否恢复？工具权限与失败重试边界写清楚了吗？'),
    ('工具与应用', r'\bmcp\b|model.context.protocol|工具调用|tool.call|computer.use|浏览器自动化',
     '工具连接与自动化', '连接外部工具会扩大能力，也会增加出错的位置。先在只读、小范围任务中检查输入输出、权限和错误返回，再决定是否接入真实工作流。',
     '来源有没有说明权限范围、敏感数据处理和工具出错后的行为？'),
    ('模型进展', r'\bgpt[- ]?\d|\bclaude\b|\bgemini\b|\bqwen\b|\bdeepseek\b|\bllama\b|\bmodels?\b|模型|推理能力',
     '模型能力与使用方式', '模型消息可以作为选型线索，实际价值仍要在自己的任务上验证。比较同一输入下的正确率、响应时间和调用限制，比只看演示更有帮助。',
     '版本、开放方式与评测条件是否明确？结果能否在同一任务上比较？'),
    ('评测与可靠性', r'\bevals?\b|evaluation|benchmark|prompt.injection|guardrail|评测|基准|提示注入|幻觉',
     '评测与可靠性', '评测结论依赖测试集和执行条件。将失败样例、重复运行的波动与成本一起看，才能判断一个改进是否适合真实任务。',
     '测试集、对照条件和失败样例是否公开？结论适用于什么任务？'),
    ('上下文与记忆', r'\brag\b|retrieval|context.engineer|context.window|\bmemory\b|检索增强|上下文|记忆管理',
     '上下文与记忆', '上下文方案值得关注的地方，是信息如何被检索、更新和引用。可用答案已知的小样本检查引用准确性，再观察漏检和过期信息的影响。',
     '引用能否追溯到原始材料？记忆如何更新、失效和删除？'),
    ('工具与应用', r'\bllm\b|\bai\b|artificial.intelligence|机器学习|人工智能|生成式|开源',
     'AI 工具与应用', '可复用的应用通常需要清楚的输入、输出和使用边界。先确认是否有公开文档或代码，再选一个结果可检查的任务试验。',
     '有没有可访问的代码、使用步骤和明确的输入输出示例？'),
]
DETAILS = [
    (r'open.source|开源', '开源'), (r'\bskills?\b|技能', '技能扩展'),
    (r'\bmcp\b|model.context.protocol', 'MCP'), (r'tool.call|工具调用', '工具调用'),
    (r'coding.agent|编程智能体', '编程智能体'), (r'claude.code', 'Claude Code'),
    (r'\bcodex\b', 'Codex'), (r'multi.agent|多智能体', '多智能体'),
    (r'\brag\b|检索增强', 'RAG'), (r'\bmemory\b|记忆', '记忆'),
    (r'context.window|上下文窗口', '上下文窗口'), (r'\bevals?\b|评测', '评测'),
    (r'benchmark|基准', '基准测试'), (r'prompt.injection|提示注入', '提示注入'),
    (r'\breasoning\b|推理', '推理'), (r'fine.tun|微调', '微调'),
    (r'quantiz|量化', '量化'), (r'\binference\b', '推理部署'),
    (r'computer.use|计算机使用', '计算机操作'), (r'workflow|工作流', '工作流'),
    (r'\bapi\b', 'API'), (r'\bpython\b', 'Python'),
]
NAMES = re.compile(r'\b(?:GPT[- ]?\d[\w.\-]*|Claude(?:[ -](?:Code|Sonnet|Opus|Haiku|[\d.]+))*|Gemini(?:[ -][\d.]+)?|Qwen[\w.\-]*|DeepSeek[\w.\-]*|Llama(?:[ -][\d.]+)?|Codex|ChatGPT|Ollama|LangGraph|vLLM)\b', re.I)
EVENT = re.compile(r'introduc|announc|launch|release|open.source|hands.on|review|benchmark|eval|guide|tutorial|how (to|we|i)|build|implement|practical|workflow|发布|开源|实测|评测|教程|实现|推出|工具|应用|模型|智能体|编程', re.I)
TITLE_FACTS = [
    (r'auto(?:matic)?[ -]eval', '原标题提到自动评测工具。'),
    (r'model guide|guide for.*gpt', '原标题是一份模型使用指南。'),
    (r'coding.agent|编程智能体', '原标题涉及编程智能体。'),
    (r'open.source|开源', '原标题涉及开源内容。'),
    (r'agent.*memory|memory.*agent', '原标题涉及智能体的记忆管理。'),
    (r'prompt.injection|提示注入', '原标题讨论提示注入。'),
]


def identity(url):
    url = daily.canonical(url)
    if not url:
        return ''
    u = urllib.parse.urlsplit(url)
    query = urllib.parse.urlencode(sorted((k, v) for k, v in urllib.parse.parse_qsl(u.query)
                                        if k not in {'fbclid', 'gclid'}))
    return urllib.parse.urlunsplit(('https', u.netloc.lower(), u.path, query, ''))


def title_key(title):
    return re.sub(r'\W', '', title.casefold())


def classify(article, now):
    published = daily.dateparse(article.get('published', ''))
    title = article.get('title', '').strip()
    if not published or not title or len(title) > 240 or len(title.split()) > 25 or not identity(article.get('url', '')):
        return None
    age = (now - published).total_seconds() / 86400
    if age < -5 / 1440 or age > 7:
        return None
    if re.search(r'funding|raises? \$|acqui[rs]|hiring|融资|收购|招聘', title, re.I):
        return None
    # A digest may mention dozens of unrelated models later in its body. Use its
    # lead, require a concrete signal in the title, and never rename it after an
    # incidental model mentioned in the feed.
    evidence = title + ' ' + article.get('excerpt', '')[:1200]
    matches = [rule for rule in RULES if re.search(rule[1], evidence, re.I)]
    if not matches:
        return None
    # General AI chatter is insufficient; require a specific theme or practical
    # signal. HN link metadata alone is not evidence of an article's content.
    specific = [rule for rule in matches if rule != RULES[-1]]
    title_matches = [rule for rule in specific if re.search(rule[1], title, re.I)]
    if not specific or not EVENT.search(title) or len(evidence) < 80:
        return None
    if not title_matches and article['source'] not in {'Hugging Face', 'OpenAI', 'Google Research', 'Microsoft Research'}:
        return None
    if article['source'].startswith('Hacker News') and not article.get('excerpt'):
        return None
    # A named model in an eval/tool article is context, not its main category.
    priority = [RULES[i] for i in (0, 2, 4, 5, 1, 3)]
    rule = next((r for r in priority if r in title_matches), specific[0])
    names = list(dict.fromkeys(m.group() for m in NAMES.finditer(title)))[:3]
    details = [label for pattern, label in DETAILS if re.search(pattern, evidence, re.I)][:5]
    score = min(len(specific), 3) + min(len(details), 3) + (5 if title_matches else 0) + max(0, 7 - age)
    if article['source'] in {'Hugging Face', 'OpenAI', 'Google Research', 'Microsoft Research'}:
        score += 2
    return dict(article, category=rule[0], score=score, _rule=rule, _names=names, _details=details)


def editorial_note(article, now):
    rule = article['_rule']
    names, details = article['_names'], article['_details']
    subject = '、'.join(names) or article['source']
    title_zh = article['title'] if daily.cjk_ratio(article['title']) > 0.15 else rule[2] + '｜' + article['title']
    topics = '、'.join(details) or rule[2]
    title_facts = ''.join(text for pattern, text in TITLE_FACTS
                          if re.search(pattern, article['title'], re.I))
    date_kind = article.get('date_kind', 'feed_published')
    date_label = {'project_created': '项目创建时间', 'source_updated': '订阅更新时间'}.get(date_kind, '来源发布时间')
    fact = f'公开来源为 {article["source"]}，{date_label}为 {article["published"]}。{title_facts}标题与订阅信息涉及{topics}。'
    if date_kind == 'project_created':
        fact += '这里的日期是 GitHub 项目创建日期，不能当作产品发布日期。'
    if date_kind == 'source_updated':
        fact += '来源只提供更新时间，不能确认首次发布时间或事件发生时间。'
    return {
        'title': article['title'], 'title_zh': title_zh, 'url': daily.canonical(article['url']),
        'source': article['source'], 'published': article['published'], 'date_kind': date_kind,
        'discovered_at': now.isoformat(), 'category': article['category'],
        'excerpt': '', 'summary': f'{title_facts}{subject}相关内容涉及{topics}。{rule[3]}',
        'reading': '## 来源事实\n\n' + fact + '\n\n## 短解读（分析）\n\n' + rule[3],
        'question': rule[4], 'tags': list(dict.fromkeys(names + details + [rule[0]]))[:5],
        'content_kind': 'brief', 'summary_kind': 'rule_based_brief',
        'evidence_kind': 'public_feed_metadata',
    }


def choose(collected, state):
    seen, titles = set(state['seen']), set(state['titles'])
    now = dt.datetime.fromisoformat(state['now'])
    ranked = [ranked for article in collected
              if identity(article.get('url', '')) not in seen
              and title_key(article.get('title', '')) not in titles
              and (ranked := classify(article, now))]
    ranked.sort(key=lambda a: (-a['score'], a['url']))
    picked, sources = [], {}
    for article in ranked:
        key, title = identity(article['url']), title_key(article['title'])
        if key in seen or title in titles or sources.get(article['source'], 0) >= 2:
            continue
        picked.append(editorial_note(article, now))
        seen.add(key); titles.add(title)
        sources[article['source']] = sources.get(article['source'], 0) + 1
        if len(picked) >= state['limit']:
            break
    return picked


def atomic_json(path, data):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(temp, path)


def worker(state_file, result_file):
    state = json.loads(state_file.read_text())
    collected, errors, successes = [], [], 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(daily.fetch, source): source[0] for source in SOURCES}
        futures[pool.submit(daily.fetch_github_new)] = 'GitHub 新项目'
        for future in concurrent.futures.as_completed(futures):
            name = futures[future]
            try:
                articles = [daily.untangle_hn(a) for a in future.result()]
                collected.extend(articles)
                successes += 1
                print(f'Source read: {name}, {len(articles)} dated entries', flush=True)
            except Exception as exc:
                errors.append(name)
                print(f'Source unavailable: {name} {type(exc).__name__}', file=sys.stderr, flush=True)
            # Checkpoint useful results even if a different network call stalls.
            atomic_json(result_file, {'articles': choose(collected, state), 'errors': errors,
                                      'successes': successes, 'entries': len(collected)})


def scan(state):
    with tempfile.TemporaryDirectory(prefix='ai-brief-') as directory:
        folder = Path(directory)
        state_file, result_file = folder / 'state.json', folder / 'results.json'
        atomic_json(state_file, state)
        try:
            subprocess.run([sys.executable, str(Path(__file__).resolve()), '--worker',
                            str(state_file), str(result_file)], timeout=SCAN_SECONDS, check=True)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
            print(f'Scan stopped within budget: {type(exc).__name__}; recovering checkpoint', file=sys.stderr)
        if not result_file.exists():
            raise RuntimeError('No source checkpoint; keeping all published data')
        result = json.loads(result_file.read_text())
        if not result['successes']:
            raise RuntimeError('All sources failed; keeping all published data')
        return result


def run(force=False, hourly=False, candidates=None):
    now = dt.datetime.now(daily.TZ)
    data = daily.ROOT / 'daily/data'
    data.mkdir(parents=True, exist_ok=True)
    target = data / f'{now.date()}.json'
    if target.exists() and not force and not hourly:
        print('Today already published; keeping edition unchanged.')
        daily.render(updated_date=str(now.date()))
        return
    current = json.loads(target.read_text()) if target.exists() else None
    existing = current['articles'] if current else []
    history = [json.loads(p.read_text()) for p in data.glob('????-??-??.json')]
    seen = sorted({identity(a['url']) for issue in history for a in issue['articles']})
    titles = sorted({title_key(a['title']) for issue in history for a in issue['articles']})
    remaining = max(0, daily.MAX_ARTICLES - len(existing))
    # Scan hourly even after the daily cap; avoid writing or calling any model.
    state = {'now': now.isoformat(), 'seen': seen, 'titles': titles,
             'limit': min(PER_RUN if hourly else 4, remaining) or 1}
    result = scan(state)
    known = set(seen)
    chosen = []
    for article in result['articles']:
        key = identity(article['url'])
        if key and key not in known and len(chosen) < remaining:
            chosen.append(article); known.add(key)
    if candidates:
        atomic_json(candidates, chosen)
        print('Candidates:', len(chosen))
        return
    if chosen:
        issue = {'date': str(now.date()), 'generated_at': dt.datetime.now(daily.TZ).isoformat(),
                 'articles': daily.merge_edition(existing, chosen, daily.MAX_ARTICLES),
                 'errors': result['errors']}
        atomic_json(target, issue)
    daily.render(updated_date=str(now.date()))
    message = f'AI discovery: {result["successes"]}/{len(SOURCES)+1} sources, {result["entries"]} dated entries; {len(chosen)} new, {len(existing)+len(chosen)} in today’s edition.'
    print(message)
    if not chosen:
        print('No qualifying unseen item (or daily cap reached); published data kept unchanged.')
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a', encoding='utf-8') as handle:
            handle.write(message + '\n\nNo model API calls or image downloads.\n')


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == '--worker':
        worker(Path(sys.argv[2]), Path(sys.argv[3]))
    else:
        raise SystemExit('Use daily.py --hourly or daily.py --force')
