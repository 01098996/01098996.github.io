import datetime as dt
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import briefs
import daily


class BriefTests(unittest.TestCase):
    now = dt.datetime(2026, 10, 5, 12, tzinfo=daily.TZ)

    def row(self, **changes):
        row = dict(title='Building Claude Code agent skills', url='https://example.com/new',
                   source='Hugging Face', published=self.now.isoformat(),
                   excerpt='A practical workflow for coding agents with skills and evals. ' * 4,
                   category='AI 编程实践')
        row.update(changes)
        return row

    def state(self, **changes):
        state = dict(now=self.now.isoformat(), seen=[], titles=[], limit=2)
        state.update(changes)
        return state

    def test_validate_dates_and_allow_practical_releases(self):
        self.assertIsNotNone(briefs.classify(self.row(title='Introducing Claude Code skills for coding agents'), self.now))
        for published in ('', 'invalid', (self.now - dt.timedelta(days=8)).isoformat(),
                          (self.now + dt.timedelta(hours=1)).isoformat()):
            self.assertIsNone(briefs.classify(self.row(published=published), self.now))
        self.assertIsNone(briefs.classify(self.row(title='AI funding news', excerpt='funding ' * 30), self.now))
        self.assertIsNone(briefs.classify(self.row(title='AI is interesting', excerpt='generic chatter ' * 20), self.now))

    def test_url_title_dedup_and_source_limit(self):
        rows = [self.row(), self.row(url='http://example.com/new/?utm_source=feed'),
                self.row(url='https://other.com/same-title'),
                self.row(title='Agent eval benchmark', url='https://example.com/two'),
                self.row(title='Practical agent tutorial', url='https://example.com/three')]
        selected = briefs.choose(rows, self.state(limit=4))
        self.assertEqual(len(selected), 2)
        self.assertEqual(len({briefs.identity(a['url']) for a in selected}), 2)
        self.assertEqual(briefs.choose([self.row()], self.state(seen=['https://example.com/new'])), [])
        self.assertEqual(briefs.choose([self.row()], self.state(titles=[briefs.title_key(self.row()['title'])])), [])

    def test_brief_render_has_honest_labels_and_no_copied_body(self):
        row = self.row(date_kind='project_created')
        note = briefs.choose([row], self.state())[0]
        self.assertEqual(note['excerpt'], '')
        self.assertNotIn('translation', note)
        self.assertNotIn('images', note)
        page = daily.article_page({'date':'2026-10-05'}, note, 1)
        cards = daily.cards({'date':'2026-10-05','articles':[note]})
        for text in ('简讯卡片', '项目创建时间', '短解读（分析）', '未阅读全文', row['url']):
            self.assertIn(text, page)
        self.assertNotIn('全文中文翻译', page)
        self.assertNotIn(row['excerpt'], page)
        self.assertIn('阅读解读', cards)
        self.assertNotIn('阅读译文', cards)
        note['date_kind'] = 'source_updated'
        updated = briefs.editorial_note(briefs.classify(self.row(date_kind='source_updated'), self.now), self.now)
        self.assertIn('不能确认首次发布时间', updated['reading'])

    def test_hard_deadline_recovers_partial_checkpoint(self):
        def stalled(command, **kwargs):
            briefs.atomic_json(Path(command[-1]), dict(articles=[], errors=['slow'], successes=1, entries=2))
            raise subprocess.TimeoutExpired(command, kwargs['timeout'])
        with patch.object(briefs.subprocess, 'run', side_effect=stalled) as run:
            result = briefs.scan(self.state())
            self.assertEqual(result['successes'], 1)
            self.assertEqual(run.call_args.kwargs['timeout'], briefs.SCAN_SECONDS)
        def failed(command, **kwargs):
            briefs.atomic_json(Path(command[-1]), dict(articles=[], errors=['all'], successes=0, entries=0))
        with patch.object(briefs.subprocess, 'run', side_effect=failed), self.assertRaises(RuntimeError):
            briefs.scan(self.state())

    def test_failed_empty_and_append_runs_preserve_history(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(daily, 'ROOT', Path(directory)):
            data = Path(directory)/'daily/data'; data.mkdir(parents=True)
            day = str(dt.datetime.now(daily.TZ).date())
            existing = dict(date=day, generated_at=day+'T09:00:00+08:00', articles=[self.row()], errors=[])
            target = data/(day+'.json'); briefs.atomic_json(target, existing)
            old_page = data.parent/'2026-09-30/01-old/index.html'
            old_page.parent.mkdir(parents=True); old_page.write_text('Do not edit')
            before = target.read_bytes()
            with patch.object(briefs, 'scan', side_effect=RuntimeError('all failed')), self.assertRaises(RuntimeError):
                briefs.run(hourly=True)
            self.assertEqual(target.read_bytes(), before)
            with patch.object(briefs, 'scan', return_value=dict(articles=[], errors=[], successes=1, entries=3)):
                briefs.run(hourly=True)
            self.assertEqual(target.read_bytes(), before)
            self.assertEqual(old_page.read_text(), 'Do not edit')
            new = briefs.choose([self.row(url='https://example.com/second')], self.state())[0]
            with patch.object(briefs, 'scan', return_value=dict(articles=[new], errors=[], successes=1, entries=3)), patch.object(daily, 'model_text', side_effect=AssertionError('No model calls')), patch.object(daily, 'download_images', side_effect=AssertionError('No image copies')), patch.object(daily, 'notify', side_effect=AssertionError('No notifications')):
                briefs.run(hourly=True)
                briefs.run(hourly=True)
            issue = json.loads(target.read_text())
            self.assertEqual(issue['articles'][0], existing['articles'][0])
            self.assertEqual(len(issue['articles']), 1)
            self.assertEqual(target.read_bytes(), before)
            draft=json.loads((Path(directory)/'scripts/discovery'/(day+'.json')).read_text())
            self.assertEqual(len(draft['articles']), 1)
            self.assertEqual(json.loads((data.parent/'latest.json').read_text())['count'], 1)
            self.assertIn('https://example.com/new', (data.parent/day/daily.art_slug(existing['articles'][0]['url'],1)/'index.html').read_text())
            self.assertEqual(old_page.read_text(), 'Do not edit')


if __name__ == '__main__':
    unittest.main()
