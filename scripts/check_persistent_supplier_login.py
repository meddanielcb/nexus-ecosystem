"""Host-only one-task probe. Leaves the managed browser and its profile open.

Requires the dedicated login page to have credentials already filled securely.
No credentials, cookies or token are printed or written by this script.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import time

CAPTURE = r'''(() => {
 let callback;
 Object.defineProperty(window, 'cf__reactTurnstileOnLoad', {
  configurable: true, get: () => callback,
  set: fn => { callback = function() {
   const render = window.turnstile.render;
   window.turnstile.render = function(container, opts) {
    if (opts.sitekey === '0x4AAAAAACFhU7XJduqvbHH2') window.__nexusCallback = opts.callback;
    return render.apply(this, arguments);
   };
   return fn.apply(this, arguments);
  }; }
 });
})();'''
ROOT = Path('/var/lib/nexus-supplier-browser')
STATE = ROOT/'solver-attempt.json'

def save(state):
    temporary=ROOT/'solver-attempt.tmp'
    fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as f:
        json.dump(state,f);f.flush();os.fsync(f.fileno())
    os.replace(temporary,STATE)

async def main(authorized):
    import httpx
    from playwright.async_api import async_playwright
    if not authorized:
        raise ValueError('Explicit authorization required')
    state=json.loads(STATE.read_text()) if STATE.exists() else None
    if state and state.get('stage')!='polling':
        print(json.dumps({'result':'attempt_not_replayed'}));return
    async with async_playwright() as p:
        browser=await p.chromium.connect_over_cdp('http://127.0.0.1:9222')
        page=next(x for x in browser.contexts[0].pages if x.url.split('?')[0]=='https://controle.vip/login')
        username=await page.locator('input[name="username"]').input_value()
        password=await page.locator('input[name="password"]').input_value()
        if not username or not password:
            print(json.dumps({'result':'credentials_not_prepared','paid_task_created':False}));return
        await page.add_init_script(CAPTURE)
        await page.reload(wait_until='domcontentloaded',timeout=45000)
        await page.locator('input[name="username"]').fill(username)
        await page.locator('input[name="password"]').fill(password)
        await page.wait_for_function("typeof window.__nexusCallback === 'function'",timeout=30000)
        key=json.loads(Path('/opt/data/nexus_playtv_bot/config_keys.json').read_text())['twocaptcha_api_key']
        async with httpx.AsyncClient(timeout=20,follow_redirects=False) as client:
            async def solver(method,data):
                response=await client.post('https://api.2captcha.com/'+method,json={'clientKey':key,**data})
                result=response.json()
                if response.status_code!=200 or result.get('errorId')!=0:
                    raise RuntimeError('Solver did not confirm operation')
                return result
            if state is None:
                state={'stage':'creating','created_at':time.time()}
                fd=os.open(STATE,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
                with os.fdopen(fd,'w') as f:json.dump(state,f);f.flush();os.fsync(f.fileno())
                created=await solver('createTask',{'task':{'type':'TurnstileTaskProxyless','websiteURL':'https://controle.vip/login','websiteKey':'0x4AAAAAACFhU7XJduqvbHH2'}})
                if type(created.get('taskId')) is not int or created['taskId']<=0:raise RuntimeError('Invalid task id')
                state.update(stage='polling',task_id=created['taskId']);save(state)
                print(json.dumps({'captcha_task':'created'}),flush=True)
            challenge=None
            for _ in range(36):
                await asyncio.sleep(5)
                result=await solver('getTaskResult',{'taskId':state['task_id']})
                if result.get('status')=='ready':
                    challenge=result.get('solution',{}).get('token');break
            if not challenge:
                print(json.dumps({'result':'solver_pending','resume_same_task':True}),flush=True);return
        state['stage']='login_attempted';save(state)
        await page.evaluate('token => window.__nexusCallback(token)',challenge)
        async with page.expect_response(lambda r:r.url=='https://api.controle.fit/api/auth/sign-in' and r.request.method=='POST',timeout=30000) as pending:
            await page.get_by_role('button',name='Entrar',exact=True).click(timeout=15000)
        response=await pending.value
        state['sign_in_status']=response.status;save(state)
        print(json.dumps({'sign_in_status':response.status}),flush=True)
        if response.status!=200:return
        payload=await response.json()
        token=payload.get('token')
        if not isinstance(token,str) or not token:raise RuntimeError('Missing token')
        # Same live browser context as login, without exporting the session.
        profile=await page.evaluate('''async token => {
            const r=await fetch('https://api.controle.fit/api/profile',{
                headers:{Authorization:'Bearer '+token,Accept:'application/json, text/plain, */*'},
                credentials:'include',redirect:'error',signal:AbortSignal.timeout(15000)
            });
            let body=null;try{body=await r.json()}catch(_){}
            return {status:r.status,body};
        }''',token)
        body=profile.get('body')
        login_user=payload.get('user',{})
        candidate=body.get('data',body) if isinstance(body,dict) else None
        match=isinstance(candidate,dict) and login_user.get('id') is not None and candidate.get('id')==login_user.get('id')
        state.update(stage='profile_checked',profile_status=profile['status'],account_matches=match)
        save(state)
        print(json.dumps({'profile_status':profile['status'],'account_matches':match,'browser_left_open':True}),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authorize-one-paid-task',action='store_true')
    args=parser.parse_args()
    try:asyncio.run(main(args.authorize_one_paid_task))
    except BaseException as e:
        print(json.dumps({'result':'not_completed','error_type':type(e).__name__}),flush=True)
        raise SystemExit(2)
