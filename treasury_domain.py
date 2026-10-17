"""Treasury contract. Exact decimal strings, independent snapshot portfolios."""
import datetime as dt
import re
from decimal import Decimal


def identifier(value):
    return isinstance(value,str) and bool(re.fullmatch(r'[A-Za-z0-9_-]{1,100}',value))


def amount(value,nullable=True):
    if value is None and nullable:return
    if not isinstance(value,str) or not re.fullmatch(r'(0|[1-9]\d{0,14})(\.\d{1,12})?',value):
        raise ValueError('资产数字格式无效，请使用非负数字且最多 12 位小数')


def validate_portfolio(p):
    if not isinstance(p,dict) or not isinstance(p.get('assets'),list) or not isinstance(p.get('accounts'),list):raise ValueError('国库数据格式错误')
    if len(p['assets'])>500 or len(p['accounts'])>5000:raise ValueError('国库账户数量超过本地版限制')
    if 'market' in p:validate_market(p['market'])
    assets={}
    for a in p['assets']:
        if not isinstance(a,dict) or not identifier(a.get('id')) or a['id'] in assets:raise ValueError('资产标识无效或重复')
        assets[a['id']]=a
        for k in ('name','symbol','unit'):
            if not isinstance(a.get(k),str) or not a[k].strip() or len(a[k])>80:raise ValueError('资产名称、简称和单位必填')
        if a.get('category') not in ('cash','crypto','investment','other') or type(a.get('archived')) is not bool:raise ValueError('资产分类或状态错误')
        if 'pricingMode' in a and a['pricingMode'] not in ('auto','manual'):raise ValueError('报价方式无效')
        if 'quoteId' in a and (not isinstance(a['quoteId'],str) or not re.fullmatch(r'[a-z0-9_-]{0,100}',a['quoteId'])):raise ValueError('币种行情标识无效')
        if a.get('pricingMode')=='auto' and (a['category']!='crypto' or not a.get('quoteId')):raise ValueError('自动报价需选择加密币种标识')
        amount(a.get('priceCny'))
        if a.get('priceCny') is not None and Decimal(a['priceCny'])<=0:raise ValueError('单价必须大于零')
        if a['category'] in ('cash','investment') and (a['priceCny']!='1' or a['unit']!='元'):raise ValueError('人民币及个人投资按人民币金额记录')
        if a.get('priceDate'):dt.date.fromisoformat(a['priceDate'])
    ids=set()
    for a in p['accounts']:
        if not isinstance(a,dict) or not identifier(a.get('id')) or a['id'] in ids:raise ValueError('账户标识无效或重复')
        ids.add(a['id'])
        if a.get('assetId') not in assets or not isinstance(a.get('name'),str) or not a['name'].strip() or len(a['name'])>100:raise ValueError('账户名称或资产关联错误')
        amount(a.get('amount'))
        if type(a.get('archived')) is not bool:raise ValueError('账户状态错误')
        if a['archived'] and a.get('amount') is not None and Decimal(a['amount'])!=0:raise ValueError('有余额的账户不能归档')
        if assets[a['assetId']]['archived'] and not a['archived'] and a.get('amount') is not None and Decimal(a['amount'])!=0:raise ValueError('有余额的资产不能归档')
        dt.datetime.fromisoformat(a['updatedAt'].replace('Z','+00:00'))
    return p


def validate_treasury(t):
    validate_portfolio(t)
    validate_market(t.get('market'))
    for k in ('changes','snapshots'):
        if not isinstance(t.get(k),list):raise ValueError('国库历史格式错误')
    if len(t['changes'])>200 or len(t['snapshots'])>2000:raise ValueError('国库历史数量超过本地版限制')
    for kind, records in (('changes',t['changes']),('snapshots',t['snapshots'])):
        ids=set()
        for r in records:
            if not isinstance(r,dict) or not identifier(r.get('id')) or r['id'] in ids:raise ValueError('国库历史标识错误')
            ids.add(r['id'])
            if not isinstance(r.get('label'),str) or not r['label'].strip():raise ValueError('盘点或修改说明不能为空')
            if kind == 'snapshots':
                validate_portfolio(r.get('portfolio'));dt.date.fromisoformat(r['date']);dt.datetime.fromisoformat(r['createdAt'].replace('Z','+00:00'))
                if not isinstance(r.get('note'),str):raise ValueError('盘点备注格式错误')
            else:
                validate_portfolio(r.get('before'));validate_portfolio(r.get('after'));dt.datetime.fromisoformat(r['at'].replace('Z','+00:00'))
    return t


def validate_market(m):
    if not isinstance(m,dict) or m.get('frequency') not in ('daily','weekly','manual'):raise ValueError('行情更新频率无效')
    def timestamp(value):
        if not isinstance(value,str):raise ValueError('行情时间无效')
        if dt.datetime.fromisoformat(value.replace('Z','+00:00')).tzinfo is None:raise ValueError('行情时间缺少时区')
    for k in ('lastAttempt','lastSuccess'):
        if m.get(k) is not None:timestamp(m[k])
    if not isinstance(m.get('errors'),list) or len(m['errors'])>502 or any(not isinstance(e,str) or len(e)>500 for e in m['errors']):raise ValueError('行情状态无效')
    if not isinstance(m.get('prices'),dict) or len(m['prices'])>1000:raise ValueError('报价集合无效')
    for key,q in m['prices'].items():
        if not re.fullmatch(r'[a-z0-9_-]{1,100}',key) or not isinstance(q,dict) or q.get('source')!='CoinGecko':raise ValueError('行情来源无效')
        amount(q.get('usd'),False)
        if Decimal(q['usd'])<=0:raise ValueError('美元报价必须大于零')
        timestamp(q['at'])
    if not isinstance(m.get('fx'),dict) or set(m['fx'])-{'USD','HKD'}:raise ValueError('汇率集合无效')
    for q in m['fx'].values():
        if not isinstance(q,dict) or q.get('source')!='Frankfurter':raise ValueError('汇率来源无效')
        amount(q.get('rate'),False)
        if Decimal(q['rate'])<=0:raise ValueError('汇率必须大于零')
        dt.date.fromisoformat(q['date'])
