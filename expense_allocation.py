"""Long-use purchase metadata. Payment dates and amounts are never replaced."""
import datetime as dt
import re

def allocation(value, *, purchase_date=None, allow_settlement=True):
    if value is None:return None
    keys={'startDate','expectedEndDate','endDate','resaleCents','resaleDate','termType','fixedEndDate'}
    if not isinstance(value,dict) or set(value)-keys or 'startDate' not in value:raise ValueError('长期使用设置无效')
    def date(v):
        if not isinstance(v,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',v) or not '1901-01-01'<=v<='2099-12-31':raise ValueError('使用日期无效')
        dt.date.fromisoformat(v);return v
    term=value.get('termType','estimated')
    if term not in ('estimated','fixed'):raise ValueError('使用期限类型无效')
    end_key='fixedEndDate' if term=='fixed' else 'expectedEndDate'
    other_key='expectedEndDate' if term=='fixed' else 'fixedEndDate'
    if end_key not in value or other_key in value:raise ValueError('请填写对应期限的结束日期')
    if term=='fixed' and any(k in value for k in ('endDate','resaleCents','resaleDate')):raise ValueError('固定期限无需使用结算；变更期限请编辑起止日期')
    start,end=date(value['startDate']),date(value[end_key])
    if end<start:raise ValueError('结束日期不能早于开始使用')
    if term!='fixed' and purchase_date and start<purchase_date:raise ValueError('开始使用不能早于付款日期')
    ended=value.get('endDate');resale=value.get('resaleCents',0)
    if type(resale) is not int or not 0<=resale<=99999999999:raise ValueError('回收金额须为非负整数分')
    if ended is not None:
        if not allow_settlement:raise ValueError('手机录入仅支持新增使用期，结算请在电脑完成')
        if date(ended)<start:raise ValueError('实际结束日期不能早于开始使用')
        if ended>dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date().isoformat():raise ValueError('实际结束日期不能晚于今天')
    elif resale:raise ValueError('请先填写实际结束日期，再登记回收金额')
    received=value.get('resaleDate')
    if received is not None:
        if not ended or not resale:raise ValueError('回收日期须同时有结算和回收金额')
        if date(received)>dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date().isoformat() or purchase_date and received<purchase_date:raise ValueError('回收到账日期无效')
    return value

def report_rows(entries,month,basis='cash'):
    """Same integer-day allocation as the desktop pure model; no state writes."""
    source={e['id']:e for e in entries}
    if basis=='cash':
        rows=[e for e in entries if not e.get('deleted') and isinstance(e.get('date'),str) and e['date'].startswith(month)]
        for e in entries:
            a=e.get('allocation')
            if e.get('deleted') or not a or not a.get('endDate') or not a.get('resaleCents') or not (a.get('resaleDate') or a['endDate']).startswith(month):continue
            rows.append({**e,'date':a.get('resaleDate') or a['endDate'],'title':e['title']+' · 回收款','kind':'refund','amountCents':a['resaleCents'],'isResale':True})
        return rows
    if basis!='usage':raise ValueError('统计口径无效')
    first=dt.date.fromisoformat(month+'-01');last=dt.date(first.year+int(first.month==12),first.month%12+1,1)
    rows=[e for e in entries if not e.get('deleted') and not e.get('allocation') and not (e['kind']=='refund' and source.get(e.get('refundOf'),{}).get('allocation')) and isinstance(e.get('date'),str) and e['date'].startswith(month)]
    for e in entries:
        if e.get('deleted') or not e.get('allocation') or e['kind']!='expense':continue
        a=e['allocation'];start=dt.date.fromisoformat(a['startDate']);end=dt.date.fromisoformat(a.get('endDate') or a.get('fixedEndDate') or a['expectedEndDate'])+dt.timedelta(days=1)
        days=(end-start).days;refunds=sum(r['amountCents'] for r in entries if not r.get('deleted') and r['kind']=='refund' and r['refundOf']==e['id'])
        net=e['amountCents']-refunds-(a.get('resaleCents',0) if a.get('endDate') else 0)
        day=max(first,start)
        while day<min(last,end):
            i=(day-start).days;amount=net*(i+1)//days-net*i//days
            rows.append({**e,'date':str(day),'kind':'refund' if amount<0 else 'expense','amountCents':abs(amount),'allocated':True})
            day+=dt.timedelta(days=1)
    return rows
