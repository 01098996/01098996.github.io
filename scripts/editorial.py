"""Validate editor-authored original bodies and publish an idempotent inbox.

This is a structural gate, not an automated fact checker. The trusted editor must
read and verify public primary sources before setting approved=true.
"""
import datetime as dt
import hashlib
import json
import re
from pathlib import Path

import daily
from briefs import atomic_json, identity

SECTIONS = ('事实与来源', '技术机制', '例子与用途', '限制与不确定性', '开发者启示')


def validate(row, now):
    if row.get('approved') is not True:
        raise ValueError('Draft is not approved')
    for key in ('source_url','source_title','source_published_at','publication_date',
                'title_zh','summary','body_markdown','category','reviewed_at','authoring_note'):
        if not isinstance(row.get(key),str) or not row[key].strip():
            raise ValueError('Missing '+key)
    url=daily.canonical(row['source_url'])
    if not url or not url.startswith('https://'):
        raise ValueError('Primary source must be an HTTPS URL')
    published=daily.dateparse(row['source_published_at'])
    reviewed=daily.dateparse(row['reviewed_at'])
    day=dt.date.fromisoformat(row['publication_date'])
    if not published or not reviewed or max(published,reviewed)>now+dt.timedelta(minutes=5):
        raise ValueError('Unverified or future date')
    if day>now.astimezone(daily.TZ).date() or (now-published).total_seconds()>7*86400:
        raise ValueError('Publication day is future or main source is older than seven days')
    body=row['body_markdown'].strip()
    if not 800<=len(body)<=6000 or sum('\u4e00'<=c<='\u9fff' for c in body)<600:
        raise ValueError('Original body must have 800-6000 characters and >=600 Chinese characters')
    if re.search(r'\[TK\]|TODO|lorem ipsum|待补充正文|占位正文',body,re.I):
        raise ValueError('Placeholder body')
    headings=list(re.finditer(r'^## (.+)$',body,re.M))
    for section in SECTIONS:
        match=next((m for m in headings if m.group(1).strip()==section),None)
        if not match: raise ValueError('Missing body section '+section)
        end=next((m.start() for m in headings if m.start()>match.start()),len(body))
        if len(body[match.end():end].strip())<60:
            raise ValueError('Body section lacks substance: '+section)
    paragraphs=[re.sub(r'\s+','',p) for p in body.split('\n\n') if len(p)>80]
    if len(paragraphs)!=len(set(paragraphs)):
        raise ValueError('Repeated filler paragraphs')
    if re.search(r'(我|我们)(亲测|实测|试用|测试了|体验了)',body):
        raise ValueError('Personal test claims need author evidence; not supported by this pipeline')
    sources=row.get('sources')
    if not isinstance(sources,list) or not sources:
        raise ValueError('Primary source list missing')
    verified=[]
    for source in sources:
        if source.get('kind')!='primary' or not source.get('title') or not source.get('publisher'):
            raise ValueError('Each source needs kind=primary, title and publisher')
        link=daily.canonical(source.get('url',''))
        if not link.startswith('https://'): raise ValueError('Unsafe source URL')
        stamp=source.get('published_at')
        if stamp is not None and (not isinstance(stamp,str) or not daily.dateparse(stamp) or daily.dateparse(stamp)>now+dt.timedelta(minutes=5)):
            raise ValueError('Invalid source publication date')
        verified.append(dict(source,url=link))
    main=next((s for s in verified if identity(s['url'])==identity(url)),None)
    if not main or main.get('published_at')!=row['source_published_at']:
        raise ValueError('Main source and its publication date must match the source list')
    if len(row['title_zh'])>160 or len(row['summary'])>500:
        raise ValueError('Headline or introduction too long')
    return dict(title=row['source_title'],title_zh=row['title_zh'],url=url,
                source=main['publisher'],published=published.isoformat(),date_kind='feed_published',
                category=row['category'],summary=row['summary'],body_markdown=body,
                tags=[t for t in row.get('tags',[]) if isinstance(t,str)][:5],
                sources=verified,reviewed_at=reviewed.isoformat(),authoring_note=row['authoring_note'],
                content_kind='article',summary_kind='source_review',evidence_kind='primary_source_review',excerpt='')


def publish():
    inbox=daily.ROOT/'scripts/editorial-inbox.json'
    if not inbox.exists(): print('No editorial inbox; nothing new published.'); return []
    document=json.loads(inbox.read_text())
    if document.get('version')!=1 or not isinstance(document.get('articles'),list):
        raise ValueError('Inbox must have version=1 and an articles array')
    data=daily.ROOT/'daily/data'; data.mkdir(parents=True,exist_ok=True)
    issues={p.stem:json.loads(p.read_text()) for p in data.glob('????-??-??.json')}
    now=dt.datetime.now(daily.TZ); changed=set(); queued=set()
    for row in document['articles']:
        try: note=validate(row,now)
        except (ValueError,TypeError,KeyError) as error:
            print('Editorial draft held:',str(error)); continue
        key=identity(note['url'])
        if key in queued: print('Duplicate inbox source held.'); continue
        queued.add(key)
        revision=hashlib.sha256(json.dumps(note,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        prior=next(((day,i,a) for day,issue in issues.items() for i,a in enumerate(issue['articles']) if identity(a['url'])==key),None)
        if prior:
            day,i,old=prior
            if old.get('editorial_revision')==revision: continue
            if row.get('update_existing') is not True or day!=row['publication_date']:
                print('Existing URL held; explicit update_existing and original publication_date required.'); continue
            note=dict(old,**note)
            for field in ('reading','why','question','translation','translation_kind','translation_source','images'):
                note.pop(field,None)
            issues[day]['articles'][i]=note
        else:
            day=row['publication_date']
            issue=issues.setdefault(day,dict(date=day,generated_at=now.isoformat(),articles=[],errors=[]))
            if len(issue['articles'])>=daily.MAX_ARTICLES: print('Daily publication cap reached; held.'); continue
            issue['articles'].append(note)
        note['editorial_revision']=revision
        issues[day]['generated_at']=now.isoformat(); changed.add(day)
    for day in sorted(changed):
        atomic_json(data/(day+'.json'),issues[day])
        daily.render(updated_date=day)
    print('Editorial publication:',len(changed),'editions updated; feed templates cannot pass this gate.')
    return sorted(changed)


if __name__=='__main__': publish()
