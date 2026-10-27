"""Optional CNY expense ledger. All money is integer fen; no treasury writes."""
import datetime
import re


def validate_expenses(state):
    if 'expenses' not in state:
        return
    x = state['expenses']
    if not isinstance(x, dict):
        raise ValueError('花销数据无效')
    def collection(key, limit):
        rows = x.get(key)
        if not isinstance(rows, list) or len(rows) > limit:
            raise ValueError('花销集合无效：' + key)
        ids = set()
        for r in rows:
            if not isinstance(r, dict) or not isinstance(r.get('id'), str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', r['id']) or r['id'] in ids:
                raise ValueError('花销标识无效或重复')
            ids.add(r['id'])
        return rows
    categories = collection('categories', 100)
    entries = collection('entries', 20000)
    bills = collection('subscriptions', 2000)
    cats = {r['id'] for r in categories}
    for c in categories:
        if not isinstance(c.get('name'), str) or not c['name'].strip() or len(c['name']) > 30 or type(c.get('archived')) is not bool:
            raise ValueError('花销用途无效')
    category_map = {c['id']:c for c in categories}
    names = set()
    for c in categories:
        parent = c.get('parentId')
        if parent is not None and (not isinstance(parent,str) or parent not in category_map):
            raise ValueError('上级分类不存在')
        key = (parent, c['name'].strip())
        if key in names:raise ValueError('同层分类名称重复')
        names.add(key)
        seen = {c['id']}
        while parent:
            if parent in seen:raise ValueError('分类不能循环嵌套')
            seen.add(parent)
            if len(seen)>5:raise ValueError('分类最多支持五级')
            parent = category_map[parent].get('parentId')
            if parent is not None and (not isinstance(parent,str) or parent not in category_map):raise ValueError('上级分类不存在')
    def date(d):
        if not isinstance(d,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',d) or not '1901-01-01' <= d <= '2099-12-31':
            raise ValueError('花销日期无效')
        datetime.date.fromisoformat(d)
    def amount(a, zero=False):
        if type(a) is not int or not (0 if zero else 1) <= a <= 99999999999:
            raise ValueError('花销金额须为整数分')
    def common(e):
        if not isinstance(e.get('title'),str) or not e['title'].strip() or len(e['title']) > 120 or e.get('categoryId') not in cats or e.get('necessity') not in ('necessary','optional','undecided') or type(e.get('deleted')) is not bool:
            raise ValueError('花销内容或分类无效')
        amount(e.get('amountCents'))
    for b in bills:
        common(b)
        date(b.get('anchorDate'))
        if b.get('cycle') not in ('monthly','yearly') or type(b.get('nextIndex')) is not int or not 0 <= b['nextIndex'] <= 2400 or type(b.get('enabled')) is not bool:
            raise ValueError('周期账单设置无效')
    by = {e['id']:e for e in entries}
    billids = {b['id'] for b in bills}
    refunds = {}
    occurrences = set()
    for e in entries:
        common(e)
        date(e.get('date'))
        for k in ('createdAt','updatedAt'):
            if not isinstance(e.get(k),str):raise ValueError('花销时间无效')
            datetime.datetime.fromisoformat(e[k].replace('Z','+00:00'))
        if e.get('allocation') is not None:
            from expense_allocation import allocation
            if e.get('kind')!='expense':raise ValueError('退款不能单独设置使用期')
            allocation(e['allocation'],purchase_date=e['date'])
        if e.get('kind') not in ('expense','refund'):
            raise ValueError('花销类型无效')
        if e['kind'] == 'refund':
            origin = by.get(e.get('refundOf'))
            if not origin or origin['kind'] != 'expense' or (not e['deleted'] and origin['deleted']) or e['date'] < origin['date'] or any(e[k] != origin[k] for k in ('categoryId','necessity')):
                raise ValueError('退款关联原消费无效')
            if not e['deleted']:refunds[origin['id']] = refunds.get(origin['id'],0) + e['amountCents']
        elif e.get('refundOf') is not None:
            raise ValueError('消费不能关联退款来源')
        if e.get('subscriptionId') is not None:
            if e['kind'] != 'expense' or e['subscriptionId'] not in billids:raise ValueError('周期账单引用无效')
            date(e.get('billedOccurrence'))
            key = (e['subscriptionId'], e['billedOccurrence'])
            if not e['deleted']:
                if key in occurrences:raise ValueError('同一期账单不能重复记账')
                occurrences.add(key)
        elif e.get('billedOccurrence') is not None:
            raise ValueError('账单日期缺少关联账单')
    if any(total > by[id]['amountCents'] for id,total in refunds.items()):
        raise ValueError('累计退款超过原消费')
    budgets = x.get('budgets')
    if not isinstance(budgets,dict) or len(budgets) > 2400:raise ValueError('月度预算无效')
    for month,b in budgets.items():
        if not isinstance(month,str) or not re.fullmatch(r'(19\d{2}|20\d{2})-(0[1-9]|1[0-2])',month) or not isinstance(b,dict):raise ValueError('预算月份无效')
        for k in ('total','optional'):
            if b.get(k) is not None:amount(b[k],True)
        if b.get('total') is not None and b.get('optional') is not None and b['optional'] > b['total']:raise ValueError('非必要支出预算不能超过总预算')
