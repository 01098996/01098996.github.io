import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import daily
import editorial


BODY = '''## 事实与来源

本测试样例模拟一篇公开工程指南的编辑稿，用于验证发布流程，不会向外部网站写入内容。事实部分应说明材料来自谁、何时发布、讨论什么问题，并把发布方的陈述与编辑的判断区分。来源可以支持一项功能的存在，但不能代替对每种实际任务的效果验证。编辑应核对主来源的日期和链接，文档没有标注发布日期时保持为空，不把抓取时间编造成新闻时间。

## 技术机制

工程文章需要解释一个具体机制怎样工作。以一个任务执行器为例，输入进入明确的状态，再由工具完成步骤，输出经检查之后才保存。状态与结果不能混为一谈：程序结束只说明流程已经退出，仍要查看输出是否满足目标。来源中的代码或参数也要结合版本和执行环境理解。编辑应把机制里的输入、处理过程和输出讲清楚，避免只列几个关键词就当作正文。

## 例子与用途

这里构造一个假设的代码维护任务作为例子，未进行真实实验。开发者提供目标文件和验收条件，执行器读取相关内容后修改文件，再运行必要检查。若检查失败，应保存失败原因并决定重试还是交给人工。交付时同时提供修改说明与验证结果，使另一位开发者能判断这个修改是否有用。这个例子用于说明设计方法，不能证明任何特定产品的性能，更不能假装是作者亲测。

## 限制与不确定性

一个结构完整的输入仍可能含有错误，所以格式校验不能替代事实核对。外部页面可能修改，示例环境也可能与生产环境不同。编辑需要确认关键结论有来源支持，对未确认的部分写明边界。自动流程可以检查正文长度、必需章节、重复段落和来源字段，但不能凭这些字段判断文字是否深入。遇到来源不足、无法复现或结果互相矛盾，应把稿件留在草稿而不是强行发布。

## 开发者启示

应先在一个可检查的小任务上验证发布契约。准备合格与不合格两种输入，确认短稿和未批准稿不会改变历史文章，然后确认合格稿能生成可访问的页面。相同输入重试应该保持结果不变，针对已发表内容的修改则需要明确标记并保留原始网址。这样的检查让编辑与部署各自承担清楚的职责，也方便发现问题后停止发布、修复稿件，再核对实际部署的结果。'''


class EditorialTests(unittest.TestCase):
    def row(self):
        now=dt.datetime.now(daily.TZ)
        stamp=(now-dt.timedelta(days=1)).isoformat()
        url='https://example.com/primary'
        return dict(approved=True,source_url=url,source_title='Engineering guide',
                    source_published_at=stamp,publication_date=str(now.date()),
                    title_zh='工程文章样例',summary='来源核对与可验证的工程流程。',body_markdown=BODY,
                    category='工作流',tags=['工程'],reviewed_at=now.isoformat(),
                    authoring_note='假设任务，未进行亲测。',sources=[dict(url=url,title='Engineering guide',publisher='Example',kind='primary',published_at=stamp)])

    def test_card_unapproved_placeholder_and_future_are_held(self):
        now=dt.datetime.now(daily.TZ)
        for change in (dict(body_markdown='一条简讯卡片'),dict(approved=False),
                       dict(body_markdown=BODY+'\n\n[TK]'),
                       dict(source_published_at=(now+dt.timedelta(days=1)).isoformat()),
                       dict(sources=[])):
            row=self.row(); row.update(change)
            with self.assertRaises(ValueError): editorial.validate(row,now)
        valid=editorial.validate(self.row(),dt.datetime.now(daily.TZ))
        self.assertEqual(valid['content_kind'],'article')
        page=daily.article_page(dict(date=str(now.date())),valid,1)
        self.assertIn('原创中文正文',page)
        self.assertIn('核对来源',page)
        self.assertNotIn('待补充',page)

    def test_publish_idempotent_and_explicit_update_preserves_url(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(daily,'ROOT',Path(folder)):
            inbox=Path(folder)/'scripts/editorial-inbox.json'; inbox.parent.mkdir()
            row=self.row()
            def write(): inbox.write_text(json.dumps(dict(version=1,articles=[row]),ensure_ascii=False))
            write(); editorial.publish()
            target=Path(folder)/'daily/data'/(row['publication_date']+'.json')
            first=target.read_bytes(); editorial.publish()
            self.assertEqual(target.read_bytes(),first)
            row['title_zh']='修订后标题'; write(); editorial.publish()
            self.assertEqual(target.read_bytes(),first)
            row['update_existing']=True; write(); editorial.publish()
            issue=json.loads(target.read_text())
            self.assertEqual(len(issue['articles']),1)
            self.assertEqual(issue['articles'][0]['title_zh'],'修订后标题')
            slug=daily.art_slug(row['source_url'],1)
            self.assertTrue((target.parent.parent/row['publication_date']/slug/'index.html').exists())
            row['approved']=False; write(); before=target.read_bytes(); editorial.publish()
            self.assertEqual(target.read_bytes(),before)


if __name__=='__main__': unittest.main()
