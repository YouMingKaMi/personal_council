"""Storage contract v8. Imported documents are content, never executable instructions."""
import datetime
import math
import re
from treasury_domain import validate_treasury


def validate(state):
    if not isinstance(state, dict) or state.get('schemaVersion') != 8:
        raise ValueError('不支持的数据版本')
    for key in ('folders', 'notes', 'tasks', 'habits', 'rules', 'templates', 'requests'):
        values = state.get(key)
        if not isinstance(values, list) or len(values) > 20000:
            raise ValueError('数据集合格式错误：' + key)
        ids = []
        for item in values:
            if not isinstance(item, dict) or not isinstance(item.get('id'), str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', item['id']):
                raise ValueError('记录缺少标识：' + key)
            ids.append(item['id'])
        if len(ids) != len(set(ids)):
            raise ValueError('重复的记录标识：' + key)
    folders = {f['id']: f for f in state['folders']}
    for f in folders.values():
        if not isinstance(f.get('name'), str) or not f['name'].strip():
            raise ValueError('文件夹名称不能为空')
        seen = {f['id']}
        parent = f.get('parent')
        while parent:
            if parent not in folders or parent in seen:
                raise ValueError('文件夹层级循环或父级不存在')
            seen.add(parent)
            parent = folders[parent].get('parent')
        if not isinstance(f.get('fields'), list):
            raise ValueError('字段集合格式错误')
        field_ids = set()
        for field in f['fields']:
            if field.get('type') not in ('text', 'number', 'date', 'select') or not field.get('id') or not field.get('name'):
                raise ValueError('自定义字段格式错误')
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', field['id']) or field['id'] in field_ids:
                raise ValueError('字段标识无效或重复')
            field_ids.add(field['id'])
            if not isinstance(field.get('options', []), list) or not all(isinstance(x, str) for x in field.get('options', [])):
                raise ValueError('字段选项格式错误')
    for n in state['notes']:
        if n.get('folder') not in folders or not isinstance(n.get('body'), str) or not isinstance(n.get('title'), str):
            raise ValueError('笔记格式或所属文件夹错误')
        if n.get('status') not in ('draft', 'done', 'imported'):
            raise ValueError('笔记状态错误')
        if not isinstance(n.get('tags'), list) or not all(isinstance(t, str) for t in n['tags']):
            raise ValueError('标签格式错误')
        if not isinstance(n.get('values', {}), dict):
            raise ValueError('字段值格式错误')
        datetime.date.fromisoformat(n['date'])
        datetime.datetime.fromisoformat(n['updatedAt'].replace('Z', '+00:00'))
        if not n['title'].strip():
            raise ValueError('笔记标题不能为空')
    for t in state['tasks']:
        if not isinstance(t.get('title'), str) or not t['title'].strip() or not isinstance(t.get('done'), bool):
            raise ValueError('任务格式错误')
        datetime.date.fromisoformat(t['date'])
    for h in state['habits']:
        target = h.get('target')
        if type(target) not in (int, float) or not math.isfinite(target) or target <= 0:
            raise ValueError('习惯目标必须大于零')
        if not isinstance(h.get('logs'), dict):
            raise ValueError('习惯记录错误')
        for day, value in h['logs'].items():
            datetime.date.fromisoformat(day)
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError('打卡数值无效')
    for h in state['habits']:
        versions = h.get('versions')
        if not isinstance(versions, list) or not versions or not isinstance(h.get('entries'), dict):
            raise ValueError('缺少版本化习惯记录')
        ids, dates = set(), set()
        for v in versions:
            if not isinstance(v.get('id'), str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', v['id']) or v['id'] in ids:
                raise ValueError('习惯版本标识重复或无效')
            ids.add(v['id'])
            datetime.date.fromisoformat(v['fromDate'])
            if v['fromDate'] in dates:
                raise ValueError('习惯生效日期重复')
            dates.add(v['fromDate'])
            if v.get('kind') not in ('number','checklist','check') or not isinstance(v.get('name'), str) or not v['name'].strip():
                raise ValueError('习惯版本类型或名称错误')
            if type(v.get('target')) not in (int,float) or not math.isfinite(v['target']) or v['target'] <= 0:
                raise ValueError('习惯版本目标错误')
            if not isinstance(v.get('unit'), str) or not isinstance(v.get('enabled'), bool) or not isinstance(v.get('days'), list) or any(type(d) is not int or not 0 <= d <= 6 for d in v['days']):
                raise ValueError('习惯版本频率错误')
            items = v.get('items', [])
            if not isinstance(items, list) or any(not isinstance(i,dict) or not isinstance(i.get('name'),str) or not i['name'].strip() or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',str(i.get('id',''))) for i in items):
                raise ValueError('勾选项目错误')
            if len({i['id'] for i in items}) != len(items):
                raise ValueError('勾选项目重复')
            if v['kind']=='check' and (v['target']!=1 or items):raise ValueError('纯打卡不设置数量或子项目')
            if v['kind'] == 'checklist' and (not items or v.get('policy') not in ('all','atleast') or v['target'] > len(items) or int(v['target']) != v['target']):
                raise ValueError('勾选目标不能超过项目数量')
        for date, entry in h['entries'].items():
            datetime.date.fromisoformat(date)
            configs = sorted((v for v in versions if v['fromDate'] <= date),key=lambda v:v['fromDate'])
            if not configs or not isinstance(entry,dict) or entry.get('versionId') != configs[-1]['id']:
                raise ValueError('记录与当日规则不一致')
            cfg = configs[-1]
            legacy=entry.get('legacy')
            if legacy is not None:
                if not isinstance(legacy,dict) or legacy.get('status') not in ('complete','incomplete','partial','rest','deferred','unknown','recorded') or not isinstance(legacy.get('raw'),str) or len(legacy['raw'])>300 or not isinstance(legacy.get('source'),str) or len(legacy['source'])>500:
                    raise ValueError('历史习惯来源无效')
            if cfg['kind'] == 'number':
                value = entry.get('value')
                if not (value is None and legacy is not None) and (type(value) not in (int,float) or not math.isfinite(value) or value < 0):
                    raise ValueError('打卡数值错误')
            elif cfg['kind']=='check':
                if type(entry.get('checked')) is not bool:raise ValueError('纯打卡记录须为明确的完成状态')
            else:
                items = entry.get('items')
                if not isinstance(items,dict) or any(k not in {i['id'] for i in cfg['items']} or type(v) is not bool for k,v in items.items()):
                    raise ValueError('勾选记录错误')
    chronicle = state.get('chronicle')
    if not isinstance(chronicle,dict) or not isinstance(chronicle.get('events'),list) or not isinstance(chronicle.get('days'),dict):
        raise ValueError('编年史格式错误')
    ids = set()
    for event in chronicle['events']:
        identifier = event.get('id')
        if not isinstance(identifier,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',identifier) or identifier in ids:
            raise ValueError('事件标识错误')
        ids.add(identifier)
        datetime.date.fromisoformat(event['date'])
        if not isinstance(event.get('text'),str) or not event['text'].strip():
            raise ValueError('事件内容不能为空')
        if event.get('endDate'):
            datetime.date.fromisoformat(event['endDate'])
            if event['endDate'] < event['date']:
                raise ValueError('事件日期区间错误')
    for day, entry in chronicle['days'].items():
        datetime.date.fromisoformat(day)
        if not isinstance(entry,dict) or type(entry.get('complete')) is not bool:
            raise ValueError('每日完成状态错误')
    for r in state['rules']:
        if r.get('folder') not in folders or r.get('frequency') not in ('daily', 'weekly', 'monthly'):
            raise ValueError('记录计划错误')
        if not isinstance(r.get('monthDay'), int) or not 1 <= r['monthDay'] <= 31:
            raise ValueError('每月日期无效')
    for r in state['rules'] + state['habits']:
        if not isinstance(r.get('name'), str) or not r['name'].strip() or not isinstance(r.get('enabled'), bool):
            raise ValueError('计划名称或启用状态无效')
        if not isinstance(r.get('days'), list) or any(type(d) is not int or not 0 <= d <= 6 for d in r['days']):
            raise ValueError('每周日期无效')
    layout = state.get('layout')
    if not isinstance(layout, list) or any(not isinstance(x, dict) or x.get('size') not in ('half', 'wide') or x.get('id') not in ('tasks', 'habits', 'writing', 'recent', 'weekly') or not isinstance(x.get('visible'), bool) for x in layout):
        raise ValueError('布局格式错误')
    if len({x['id'] for x in layout}) != len(layout):
        raise ValueError('布局卡片重复')
    if not isinstance(state.get('pins'), list) or any(x not in folders and not any(n['id'] == x for n in state['notes']) for x in state['pins']):
        raise ValueError('置顶入口无效')
    for t in state['templates']:
        if not isinstance(t.get('name'), str) or not isinstance(t.get('body'), str) or (t.get('folder') is not None and t.get('folder') not in folders):
            raise ValueError('模板格式错误')
    for r in state['requests']:
        if not isinstance(r.get('title'), str) or not isinstance(r.get('detail'), str):
            raise ValueError('功能想法格式错误')
    if not isinstance(state.get('importInfo'), dict) or type(state['importInfo'].get('count')) is not int:
        raise ValueError('导入信息格式错误')
    if not isinstance(state.get('settings'), dict):
        raise ValueError('设置格式错误')
    from monthly_domain import validate_monthly
    validate_monthly(state)
    orders=state['settings'].get('cardOrder')
    if not isinstance(orders,dict) or len(orders)>500:raise ValueError('卡片排序设置无效')
    for group,ids in orders.items():
        if not isinstance(group,str) or not re.fullmatch(r'[A-Za-z0-9_:-]{1,160}',group) or not isinstance(ids,list) or len(ids)>20000 or any(not isinstance(x,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',x) for x in ids) or len(ids)!=len(set(ids)):
            raise ValueError('卡片排序项目无效')
    validate_treasury(state.get('treasury'))
    return state
