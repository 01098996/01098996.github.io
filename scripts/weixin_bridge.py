#!/usr/bin/env python3
"""Standalone text-only iLink bridge, based on Tencent's documented wire format.
No OpenClaw dependency. Private credentials MUST live outside the website checkout.
"""
import argparse, base64, datetime as dt, hashlib, json, os, secrets, sys, time
import urllib.parse, urllib.request
from pathlib import Path

API='https://ilinkai.weixin.qq.com'
VERSION='2.4.8'
ROOT=Path(__file__).resolve().parents[1]

def trusted_api(url):
    u=urllib.parse.urlsplit(url)
    if u.scheme!='https' or not u.hostname or not (u.hostname=='ilinkai.weixin.qq.com' or u.hostname.endswith('.ilinkai.weixin.qq.com')) or u.username or u.port not in (None,443) or u.path not in ('','/'):
        raise ValueError('Unrecognized iLink API origin')
    return url.rstrip('/')

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): raise RuntimeError('Unexpected API redirect')

def api(endpoint,payload=None,token=None,base=API,timeout=40):
    headers={'Content-Type':'application/json','AuthorizationType':'ilink_bot_token','X-WECHAT-UIN':base64.b64encode(str(secrets.randbits(32)).encode()).decode(),'iLink-App-Id':'bot','iLink-App-ClientVersion':str((2<<16)|(4<<8)|8)}
    if token: headers['Authorization']='Bearer '+token
    if payload is not None:
        payload={**payload,'base_info':{'channel_version':VERSION,'bot_agent':'CharlesDaily/1.0'}}
    request=urllib.request.Request(trusted_api(base)+'/'+endpoint,data=json.dumps(payload).encode() if payload is not None else None,headers=headers)
    with urllib.request.build_opener(NoRedirect).open(request,timeout=timeout) as r: data=json.load(r)
    if data.get('ret',0)!=0 or data.get('errcode',0)!=0:
        raise RuntimeError('iLink rejected request, code '+str(data.get('errcode',data.get('ret'))))
    return data

def save(path,state):
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    temp=path.with_suffix('.tmp')
    fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as f: json.dump(state,f)
    os.chmod(temp,0o600); os.replace(temp,path)

def state_path(value):
    p=Path(value).expanduser().resolve()
    if p==ROOT or ROOT in p.parents: raise ValueError('State must be outside the public repository')
    return p

def start_login(path,qr_path):
    if path.exists() and json.loads(path.read_text()).get('token'):
        raise RuntimeError('Already paired. Use a different state path to pair another account.')
    data=api('ilink/bot/get_bot_qrcode?bot_type=3',{'local_token_list':[]})
    if not data.get('qrcode') or not data.get('qrcode_img_content'): raise RuntimeError('Missing QR code')
    save(path,{'qr':data['qrcode'],'qr_created':time.time(),'api':API})
    import qrcode
    from qrcode.image.pure import PyPNGImage
    qr_path=Path(qr_path); qr_path.parent.mkdir(parents=True,exist_ok=True)
    qrcode.make(data['qrcode_img_content'],image_factory=PyPNGImage).save(str(qr_path))
    print('Scan the QR image with WeChat and confirm the pairing on your phone.',flush=True)

def complete_login(path,seconds):
    state=json.loads(path.read_text()); deadline=time.monotonic()+seconds
    if state.get('token'): print('Already paired.'); return
    while time.monotonic()<deadline:
        if time.time()-state['qr_created']>300: raise RuntimeError('QR code expired; generate a new one')
        result=api('ilink/bot/get_qrcode_status?'+urllib.parse.urlencode({'qrcode':state['qr']}),base=state['api'])
        status=result.get('status')
        if status=='confirmed':
            if not all(result.get(k) for k in ('bot_token','ilink_user_id')): raise RuntimeError('Incomplete login response')
            state={'token':result['bot_token'],'owner':result['ilink_user_id'],'api':trusted_api(result.get('baseurl') or API),'cursor':'','subscribed':True,'sent':[]}
            save(path,state); print('Paired. Send 日报 to the new WeChat bot to establish the reply context.',flush=True); return
        if status=='scaned_but_redirect':
            state['api']=trusted_api('https://'+result['redirect_host']); save(path,state)
        elif status in ('need_verifycode','verify_code_blocked','expired','binded_redirect'):
            raise RuntimeError('Pairing requires user action: '+status)
        time.sleep(2)
    print('Waiting for phone confirmation; run login-wait again.',flush=True)

def receive(state):
    result=api('ilink/bot/getupdates',{'get_updates_buf':state.get('cursor','')},token=state['token'],base=state['api'])
    requested=False
    for msg in result.get('msgs',[]):
        if msg.get('from_user_id')!=state['owner'] or msg.get('message_type')!=1: continue
        if msg.get('context_token'): state['context']=msg['context_token']
        for item in msg.get('item_list',[]):
            text=item.get('text_item',{}).get('text','').strip()
            if text=='停止日报': state['subscribed']=False
            elif text in ('日报','订阅日报'):
                state['subscribed']=True; requested=True
    state['cursor']=result.get('get_updates_buf',state.get('cursor',''))
    return requested

def latest(site):
    u=urllib.parse.urlsplit(site)
    if u.scheme!='https' or not u.hostname: raise ValueError('Reading site must use HTTPS')
    req=urllib.request.Request(site.rstrip('/')+'/daily/latest.json',headers={'Cache-Control':'no-cache'})
    with urllib.request.urlopen(req,timeout=20) as r:
        if urllib.parse.urlsplit(r.url).scheme!='https': raise ValueError('Site redirects away from HTTPS')
        issue=json.load(r)
    date=dt.date.fromisoformat(issue['date'])
    if (dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date()-date).days not in range(0,8): raise ValueError('Latest edition is stale or future-dated')
    # Construct destination ourselves; never send arbitrary URLs from a fetched manifest.
    issue['url']=site.rstrip('/')+'/daily/'+str(date)+'/'
    if not isinstance(issue.get('count'),int) or not isinstance(issue.get('titles'),list): raise ValueError('Invalid edition')
    return issue

def send_edition(path,state,issue):
    date=issue['date']
    if date in state.get('sent',[]) or not state.get('subscribed') or not state.get('context'): return False
    if state.get('pending'): raise RuntimeError('Earlier send outcome unknown; inspect WeChat before clearing pending state')
    text='AI 日报 · '+date+'\n'+str(issue['count'])+' 篇精选\n\n'+'\n'.join('• '+str(t)[:100] for t in issue['titles'][:5])+'\n\n阅读全文：'+issue['url']+'\n\n回复「停止日报」可暂停。'
    client='charles-daily-'+hashlib.sha256((state['owner']+date).encode()).hexdigest()[:24]
    state['pending']={'date':date,'client_id':client}; save(path,state)
    api('ilink/bot/sendmessage',{'msg':{'from_user_id':'','to_user_id':state['owner'],'client_id':client,'message_type':2,'message_state':2,'context_token':state['context'],'item_list':[{'type':1,'text_item':{'text':text}}]}},token=state['token'],base=state['api'],timeout=20)
    state.setdefault('sent',[]).append(date); state['sent']=state['sent'][-90:]; state.pop('pending',None); save(path,state)
    print('WeChat accepted edition '+date,flush=True); return True

def main():
    p=argparse.ArgumentParser(); p.add_argument('command',choices=['login-start','login-wait','once','watch']); p.add_argument('--state',required=True); p.add_argument('--qr'); p.add_argument('--site',default='https://01098996.github.io'); p.add_argument('--seconds',type=int,default=50); a=p.parse_args(); path=state_path(a.state)
    if a.command=='login-start':
        if not a.qr: p.error('--qr is required')
        start_login(path,a.qr); return
    if a.command=='login-wait': complete_login(path,a.seconds); return
    state=json.loads(path.read_text())
    if not state.get('token'): raise RuntimeError('Finish QR login first')
    checked=0
    while True:
        try:
            requested=receive(state); save(path,state)
            if requested or time.monotonic()-checked>300:
                issue=latest(a.site); send_edition(path,state,issue); checked=time.monotonic()
        except Exception as e:
            # Do not print response bodies, owner identifiers or tokens.
            print('Bridge needs attention: '+type(e).__name__,flush=True)
            if a.command=='once': raise SystemExit(1)
            time.sleep(30)
        if a.command=='once': return
        time.sleep(2)
if __name__=='__main__':
    try: main()
    except Exception as e:
        print('Stopped: '+str(e) if isinstance(e,(ValueError,RuntimeError)) else 'Stopped: '+type(e).__name__,file=sys.stderr); raise SystemExit(1)
