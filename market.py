"""Fixed-provider market data. Only public coin IDs / currency codes leave this Mac."""
import copy
import datetime as dt
import json
import re
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal, ROUND_HALF_UP, localcontext
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from repository import Conflict

UTC = dt.timezone.utc
from market_defaults import empty_market, COINS

def stamp(value):
    return dt.datetime.fromisoformat(value.replace('Z','+00:00'))

def due(m, now, force=False):
    if m['lastAttempt']:
        age=(now-stamp(m['lastAttempt'])).total_seconds()
        if age<60: return False  # Also debounce repeated explicit requests.
    if force:return True
    if m['frequency']=='manual':return False
    if m['lastAttempt'] and (now-stamp(m['lastAttempt'])).total_seconds()<3600:return False
    if not m['lastSuccess'] or m['errors']:return True
    return (now-stamp(m['lastSuccess'])).total_seconds()>=(86400 if m['frequency']=='daily' else 604800)

def positive(value):
    if isinstance(value,bool) or not isinstance(value,(int,float,Decimal,str)):raise ValueError('行情数字无效')
    with localcontext() as ctx:
        ctx.prec=50
        n=Decimal(str(value))
        if not n.is_finite() or n<=0 or n>=Decimal('1000000000000000'):raise ValueError('行情价格不在有效范围')
        n=n.quantize(Decimal('0.000000000001'),rounding=ROUND_HALF_UP)
        if n<=0:raise ValueError('行情价格精度不足')
        return format(n,'f').rstrip('0').rstrip('.')

def fetch_json(url):
    request=Request(url,headers={'User-Agent':'PersonalLedger/0.4 (local personal use)','Accept':'application/json'})
    with urlopen(request,timeout=12) as response:
        if response.url.split('/')[2] != url.split('/')[2]:raise ValueError('行情来源发生变化')
        data=response.read(1_000_001)
        if len(data)>1_000_000:raise ValueError('行情响应过大')
        return json.loads(data,parse_float=Decimal)

def error_text(provider,error):
    if isinstance(error,HTTPError):
        if error.code==429:return provider+'请求受限，稍后重试；继续使用已有价格。'
        if error.code in (401,403):return provider+'暂不允许访问，继续使用已有价格或切换手动。'
    if isinstance(error,ValueError):return provider+'返回的数据未通过校验，保留已有价格。'
    return provider+'暂时连接失败，保留已有价格。'

def fetch_market(t, now, fetch=fetch_json):
    ids=sorted({a.get('quoteId') for a in t['assets'] if a['category']=='crypto' and not a['archived'] and a.get('pricingMode')=='auto' and a.get('quoteId')})
    result={'prices':{},'fx':{},'errors':[]}
    def coins():
        url='https://api.coingecko.com/api/v3/simple/price?'+urlencode({'ids':','.join(ids),'vs_currencies':'usd','include_last_updated_at':'true','precision':'12'})
        try:
            raw=fetch(url)
            for key in ids:
                try:
                    item=raw[key]; at=dt.datetime.fromtimestamp(item['last_updated_at'],UTC)
                    if not 0 <= (now-at).total_seconds()+300 <= 86700:raise ValueError('行情过期')
                    result['prices'][key]={'usd':positive(item['usd']),'at':at.isoformat(),'source':'CoinGecko'}
                except (ValueError,KeyError,TypeError,OverflowError):result['errors'].append('CoinGecko 未提供 '+key+' 的有效近期报价，保留已有价格。')
        except Exception as e:result['errors'].append(error_text('CoinGecko',e))
    def fx(currency):
        try:
            raw=fetch('https://api.frankfurter.dev/v2/rate/'+currency.lower()+'/cny')
            date=dt.date.fromisoformat(raw['date'])
            if raw['base']!=currency or raw['quote']!='CNY' or not 0<=(now.date()-date).days<=14:raise ValueError('汇率日期或货币不符')
            return currency,{'rate':positive(raw['rate']),'date':date.isoformat(),'source':'Frankfurter'},None
        except Exception as e:return currency,None,error_text(currency+' 汇率',e)
    with ThreadPoolExecutor(max_workers=3) as pool:
        coin_job=pool.submit(coins) if ids else None
        jobs=[pool.submit(fx,c) for c in ('USD','HKD')]
        if coin_job:coin_job.result()
        for job in jobs:
            c,value,error=job.result()
            if error:result['errors'].append(error)
            else:result['fx'][c]=value
    return result

def merge_market(m,result,now):
    updated=copy.deepcopy(m)
    # Never roll back an accepted price to an older provider timestamp.
    for key,q in result['prices'].items():
        if key not in m['prices'] or stamp(q['at'])>=stamp(m['prices'][key]['at']):updated['prices'][key]=q
    for key,q in result['fx'].items():
        if key not in m['fx'] or q['date']>=m['fx'][key]['date']:updated['fx'][key]=q
    updated['lastAttempt']=now.isoformat();updated['errors']=result['errors']
    if not result['errors']:updated['lastSuccess']=now.isoformat()
    return updated

def portfolio(t):
    return copy.deepcopy({k:t[k] for k in ('assets','accounts','market') if k in t})

def effective_price(p,a):
    m=p.get('market',{});q=m.get('prices',{}).get(a.get('quoteId'));fx=m.get('fx',{}).get('USD')
    if a.get('pricingMode')=='auto' and a['category']=='crypto' and q and fx:
        with localcontext() as ctx:
            ctx.prec=60
            return format((Decimal(q['usd'])*Decimal(fx['rate'])).quantize(Decimal('0.000000000001'),rounding=ROUND_HALF_UP),'f'),stamp(q['at']).astimezone(dt.timezone(dt.timedelta(hours=8))).date().isoformat()
    return a['priceCny'],a.get('priceDate')

class MarketService:
    def __init__(self,repo,fetch=fetch_json):
        self.repo=repo;self.fetch=fetch;self.locks={'main':threading.Lock(),'lab':threading.Lock()}
    def refresh(self,space,revision,force=False):
        from domain import validate
        with self.locks[space]:
            current=self.repo.read(space)
            if current['revision']!=revision:raise Conflict('另一窗口已保存更新，请重新载入后重试。')
            now=dt.datetime.now(UTC);t=current['state']['treasury']
            if not due(t['market'],now,force):return dict(current,refreshed=False)
            result=fetch_market(t,now,self.fetch)
            updated=merge_market(t['market'],result,now)
            before=portfolio(t);t['market']=updated
            if before['market']['prices']!=updated['prices'] or before['market']['fx']!=updated['fx']:
                t['changes'].append({'id':str(uuid.uuid4()),'at':now.isoformat(),'label':'更新公开行情与汇率','before':before,'after':portfolio(t)})
                t['changes']=t['changes'][-200:]
            validate(current['state'])
            # A concurrent edit wins: return a conflict instead of overwriting it.
            current['revision']=self.repo.save(space,revision,current['state'])
            return dict(current,refreshed=True)
