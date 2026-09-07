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
        self.assertNotIn('<script>',daily.cards(issue))
    def test_empty_and_archive(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(daily,'ROOT',Path(directory)):
            data=Path(directory)/'daily/data'; data.mkdir(parents=True)
            for day in ('2026-09-06','2026-09-07'):
                (data/(day+'.json')).write_text(json.dumps({'date':day,'generated_at':day+'T09:07:00+08:00','articles':[],'errors':[]}))
            daily.render()
            self.assertIn('今天没有', (data.parent/'index.html').read_text())
            self.assertEqual(json.loads((data.parent/'latest.json').read_text())['date'],'2026-09-07')
            self.assertIn('2026-09-06', (data.parent/'archive.html').read_text())

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
