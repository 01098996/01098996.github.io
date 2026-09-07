import datetime as dt, json, tempfile, unittest
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
        c=dict(_fulltext='word '*5000)
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
