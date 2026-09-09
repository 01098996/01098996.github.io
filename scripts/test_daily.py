import datetime as dt, json, re, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import daily
import weixin_bridge as bridge

class DailyTests(unittest.TestCase):
    def test_dedup_age_diversity(self):
        now=dt.datetime(2026,9,7,tzinfo=dt.timezone.utc)
        def row(n,source='A',days=0): return dict(title='Building coding agents '+str(n),url='https://example.com/'+str(n),source=source,published=(now-dt.timedelta(days=days)).isoformat(),excerpt='Agent evals and memory')
        rows=[row(1),row(1),row(2),row(3),row(4,'B'),row(5,'C',20),row(6,'C',-2)]
        chosen=daily.select(rows,{'https://example.com/2'},now)
        self.assertEqual({a['url'] for a in chosen},{'https://example.com/1','https://example.com/3','https://example.com/4'})
    def test_url_and_html_safety(self):
        self.assertEqual(daily.canonical('javascript:alert(1)'),'')
        self.assertEqual(daily.canonical('https://example.com/x/?utm_source=x#foo'),'https://example.com/x')
        self.assertEqual(daily.plain('<p>Hello</p><script>bad()</script>'),'Hello')
        issue={'date':'2026-09-07','articles':[dict(title='<script>alert(1)</script>',url='https://example.com/',category='Agent',source='A',published='2026-09-07',excerpt='<img src=x onerror=x>')]}
        html=daily.cards(issue)
        self.assertNotIn('<script>',html)
        self.assertIn('/daily/2026-09-07/01-',html)
    def test_empty_and_archive(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(daily,'ROOT',Path(directory)):
            data=Path(directory)/'daily/data'; data.mkdir(parents=True)
            for day in ('2026-09-06','2026-09-07'):
                (data/(day+'.json')).write_text(json.dumps({'date':day,'generated_at':day+'T09:07:00+08:00','articles':[],'errors':[]}))
            daily.render()
            self.assertIn('今天没有', (data.parent/'index.html').read_text())
            self.assertEqual(json.loads((data.parent/'latest.json').read_text())['date'],'2026-09-07')
            self.assertIn('2026-09-06', (data.parent/'archive.html').read_text())
            sm=(Path(directory)/'sitemap.xml').read_text()
            self.assertIn('/daily/tags.html',sm)
            self.assertIn('sitemaps.org/schemas/sitemap',sm)
            self.assertIn('/daily/tags.html">标签',(data.parent/'index.html').read_text())
            self.assertIn('sitemap',(Path(directory)/'sitemap.xml').read_text()[:200])
    def test_render_writes_article_pages(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(daily,'ROOT',Path(directory)):
            data=Path(directory)/'daily/data'; data.mkdir(parents=True)
            article=dict(title='An agent post',url='https://example.com/post',category='Agent 开发',source='A',published='2026-09-07T00:00:00+00:00',excerpt='lead text',title_zh='标题',summary='摘要',translation='第一段\n\n```python\nprint(1)\n```',translation_kind='full')
            (data/'2026-09-07.json').write_text(json.dumps({'date':'2026-09-07','generated_at':'2026-09-07T09:07:00+08:00','articles':[article],'errors':[]},ensure_ascii=False))
            daily.render()
            slug=daily.art_slug('https://example.com/post',1)
            page=(data.parent/'2026-09-07'/slug/'index.html').read_text()
            self.assertIn('原文链接',page)
            self.assertIn('标题',page)
            self.assertIn('<pre><code>',page)
            self.assertIn('版权归原作者',page)
    def test_slug_is_stable_and_escaped(self):
        self.assertEqual(daily.art_slug('https://example.com/x',1),daily.art_slug('https://example.com/x',1))
        self.assertTrue(daily.art_slug('https://example.com/x',2).startswith('02-'))
        self.assertIn('&lt;img&gt;',daily.render_translation('<img>'))
        page=daily.article_page({'date':'2026-09-07','articles':[]},dict(title='<b>x</b>',url='https://example.com/<>',category='c',source='s',published='2026-09-07'),1)
        self.assertNotIn('<b>x</b>',page)
    def test_no_markdown_links_rendered(self):
        html=daily.render_translation('可以从[这里](https://example.com/x)下载')
        self.assertNotIn('href',html)
        self.assertIn('这里',html)
    def test_image_markers(self):
        html=daily.render_translation('开头段\n\n[[IMG1]]\n\n结尾段',['img/1.jpg','img/2.png'])
        self.assertIn('<figure><img src="img/1.jpg"',html)
        self.assertIn('img/2.png',html)
        self.assertNotIn('IMG1',html)
        html2=daily.render_translation('没有标记的译文',['img/1.jpg'])
        self.assertIn('<figure><img src="img/1.jpg"',html2)
        html3=daily.render_translation('越界标记 [[IMG3]] 结束',['img/1.jpg'])
        self.assertNotIn('IMG3',html3)
        self.assertNotIn('img/2.png',html3)
    def test_related_sidebar(self):
        seq=[('2026-09-0'+str(day),i,dict(title='Agent post '+str(day)+'-'+str(i),url='https://example.com/'+str(day)+str(i),category='Agent 开发',source='S',published='2026-09-0'+str(day),title_zh='智能体文章'+str(day)+str(i))) for day in (6,7) for i in (1,2)]
        picks=daily.related_for(seq,0)
        self.assertEqual(len(picks),min(5,len(seq)-1))
        self.assertTrue(all(p['url'].startswith('/daily/') for p in picks))
        self.assertTrue(all(p['url']!='/daily/2026-09-06/'+daily.art_slug(seq[0][2]['url'],1)+'/' for p in picks))
        issue={'date':'2026-09-06','articles':[seq[0][2]]}
        html=daily.article_page(issue,seq[0][2],1,related=picks)
        self.assertIn('相关阅读',html)
        self.assertIn('sideblock',html)
        self.assertIn('page wide',html)
    def test_untangle_hn(self):
        a=daily.untangle_hn(dict(source='Hacker News',url='https://example.com/post',excerpt='Article URL: https://example.com/post Comments URL: https://news.ycombinator.com/item?id=1 Points: 156'))
        self.assertEqual(a['url'],'https://example.com/post')
        self.assertEqual(a['discussion'],'https://news.ycombinator.com/item?id=1')
        self.assertEqual(a['excerpt'],'')
        b=daily.untangle_hn(dict(source='Hugging Face',url='https://example.com/a',excerpt='x'))
        self.assertEqual(b['excerpt'],'x'); self.assertNotIn('discussion',b)
    def test_reflow_joins_wrapped_lines(self):
        raw='我们之前曾指出，虽然现在让编程 agent 达到某个质量门槛比以往更容易，\n但软件质量似乎正在变差\n\n，这说明默认配置可能效果不佳。\n我们将复用\n此前讨论过的 Zstd 实现评测。'
        out=daily.reflow(raw)
        self.assertNotIn('\n\n，',out)
        self.assertIn('但软件质量似乎正在变差，这说明默认配置可能效果不佳。',out)
        self.assertIn('我们将复用此前讨论过的 Zstd 实现评测。',out)
        kept=daily.reflow('第一段到这里结束。\n- 列表项保持独立\n第二段。')
        self.assertIn('- 列表项保持独立',kept)
    def test_render_merges_fragments(self):
        html=daily.render_translation('但软件质量似乎正在变差\n\n，这说明默认配置可能效果不佳。')
        self.assertNotIn('<p>，这说明',html)
        self.assertIn('变差，这说明',html)
    def test_announcement_filter_and_depth(self):
        now=dt.datetime(2026,9,8,tzinfo=dt.timezone.utc)
        def row(title,excerpt='x'*700): return dict(title=title,url='https://e.com/'+re.sub(r'\W','',title)[:14],source='A',published=now.isoformat(),excerpt=excerpt)
        self.assertIsNone(daily.rank(row('Introducing GPT-6 Astra for developers'),now))
        self.assertIsNone(daily.rank(row('Announcing v2.1 of our agent framework'),now))
        self.assertIsNone(daily.rank(row('Now available: structured outputs'),now))
        deep=daily.rank(row('A hands-on review of building coding agents: lessons and pitfalls',excerpt='we benchmark agent memory workflows and evals '*30),now)
        self.assertIsNotNone(deep); self.assertGreater(deep['score'],5)
        self.assertFalse(daily.depth_ok({'_fulltext':'short'}))
        self.assertTrue(daily.depth_ok({'_fulltext':'x'*2500}))
    def test_trim_boilerplate_and_markdown(self):
        body='Back to Articles\nUpvote\n+70\niamleonie\n'+'但是正文段落足够长，包含大量中文内容，用来模拟真实的文章正文行，必须超过一百五十个字符的长度阈值才会被保留下来，这里是填充句子。'*3+'\nShare\n1 234'
        trimmed=daily.trim_boilerplate(body)
        self.assertNotIn('Upvote',trimmed); self.assertNotIn('iamleonie',trimmed); self.assertNotIn('Share',trimmed)
        html=daily.render_translation('## 标题\n\n**加粗**和`代码`词\n\n```py\nx=1\n```')
        self.assertIn('<h3>标题</h3>',html); self.assertIn('<strong>加粗</strong>',html); self.assertIn('<code>代码</code>',html)
    def test_translation_skip_rules(self):
        a=dict(_fulltext='这是一段足够长的中文正文，' * 40); daily.translate_one(a,(None,None,None))
        self.assertEqual(a['translation_kind'],'original')
        b=dict(_fulltext='short'); daily.translate_one(b,(None,None,None))
        self.assertEqual(b['translation_kind'],'unavailable')
        c=dict(title='t',_fulltext='word '*5000)
        with patch('urllib.request.urlopen',side_effect=OSError('offline')):
            daily.translate_one(c,('k','https://example.com','m'))
        self.assertEqual(c['translation_kind'],'failed')

class PushTests(unittest.TestCase):
    def test_notify_serverchan_payload(self):
        issue={'date':'2026-09-07','articles':[dict(title='T',url='https://example.com/a',title_zh='中文标题')]}
        captured={}
        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self,*args): return False
            def read(self): return b'{}'
        def fake(req,timeout):
            captured['url']=req.full_url; captured['data']=json.loads(req.data.decode()); return FakeResponse()
        with patch.dict('os.environ',{'WECHAT_PUSH_KEY':'SCT123','DAILY_SITE_URL':'https://z-xj.com'}),patch('urllib.request.urlopen',fake):
            daily.notify(issue)
        self.assertTrue(captured['url'].startswith('https://sctapi.ftqq.com/SCT123.send'))
        self.assertIn('中文标题',captured['data']['desp'])
        self.assertIn('https://z-xj.com/daily/2026-09-07/01-',captured['data']['desp'])
    def test_notify_skipped_without_key_or_articles(self):
        with patch.dict('os.environ',{},clear=True):
            self.assertIsNone(daily.notify({'date':'2026-09-07','articles':[dict(title='t',url='u')]}))
        with patch.dict('os.environ',{'WECHAT_PUSH_KEY':'SCT1'}):
            self.assertIsNone(daily.notify({'date':'2026-09-07','articles':[]}))

class WeixinTests(unittest.TestCase):
    def test_reject_credential_redirects_and_public_state(self):
        for url in ('http://ilinkai.weixin.qq.com','https://ilinkai.weixin.qq.com.evil.com','https://evil.com','https://u@ilinkai.weixin.qq.com'):
            with self.assertRaises(ValueError): bridge.trusted_api(url)
        with self.assertRaises(ValueError): bridge.state_path(str(bridge.ROOT/'state.json'))
    def test_other_senders_cannot_subscribe(self):
        state={'token':'t','api':bridge.API,'owner':'owner','subscribed':False}
        with patch.object(bridge,'api',return_value={'msgs':[{'from_user_id':'stranger','message_type':1,'context_token':'bad','item_list':[{'text_item':{'text':'日报'}}]}]}):
            self.assertFalse(bridge.receive(state)); self.assertNotIn('context',state)
    def test_success_and_uncertain_send_dedup(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'private/state.json'; state={'token':'t','api':bridge.API,'owner':'owner','subscribed':True,'context':'c','sent':[]}
            issue={'date':'2026-09-07','titles':['A'],'url':'https://example.com/daily/2026-09-07/','count':1}
            with patch.object(bridge,'api',return_value={}) as api:
                self.assertTrue(bridge.send_edition(path,state,issue)); self.assertFalse(bridge.send_edition(path,state,issue)); self.assertEqual(api.call_count,1)
            issue['date']='2026-09-08'
            with patch.object(bridge,'api',side_effect=TimeoutError):
                with self.assertRaises(TimeoutError): bridge.send_edition(path,state,issue)
            self.assertIn('pending',json.loads(path.read_text()))
            with self.assertRaises(RuntimeError): bridge.send_edition(path,state,issue)
            self.assertEqual(path.stat().st_mode & 0o777,0o600)
if __name__=='__main__': unittest.main()
