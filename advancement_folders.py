"""Keep advancement identity separate from, and linked to, its resource folder."""
import uuid
from advancement_domain import text


def science_root(state,create=False):
    a=state['advancement'];folders=state['folders']
    root=next((f for f in folders if f['id']==a.get('scienceRootId')),None)
    if not root:
        candidates=[f for f in folders if f['name']=='中科院' and not f.get('module')]
        if len(candidates)>1:
            if create:raise ValueError('有多个中科院，请先明确领域的创建位置')
            return None
        root=candidates[0] if candidates else None
    if root is None and create:
        root={'id':str(uuid.uuid4()),'name':'中科院','parent':None,'fields':[],'icon':'atom','description':''};folders.append(root)
    if root:a['scienceRootId']=root['id']
    return root


def child_folder(state,parent,name):
    name=text(name,80,True).strip()
    matches=[f for f in state['folders'] if f.get('parent')==parent['id'] and f['name']==name]
    if len(matches)>1:raise ValueError('此位置有多个同名文件夹，请先整理或选择具体文件夹')
    if matches:
        if matches[0].get('module'):raise ValueError('同名位置是功能模块，请使用其他领域名称')
        return matches[0]
    f={'id':str(uuid.uuid4()),'name':name,'parent':parent['id'],'fields':[],'icon':'folder','description':''}
    state['folders'].append(f);return f


def new_domain(state,c):
    a=state['advancement'];root=science_root(state)
    requested=text(c.get('name',''),80).strip()
    f=next((f for f in state['folders'] if f['id']==c.get('folderId')),None)
    if c.get('folderId') and f is None:raise ValueError('资料空间不存在')
    # Old clients used folderId for both the parent and the existing folder.
    # A named child of the science department must not alias that department.
    if f and (root and f['id']==root['id'] or f['name']=='中科院'):
        if not requested or requested==f['name']:raise ValueError('请选择具体领域的文件夹，或填写要新建的领域名称')
        a['scienceRootId']=f['id'];f=child_folder(state,f,requested)
    elif f is None:
        parent=next((f for f in state['folders'] if f['id']==c.get('parentId')),None)
        if c.get('parentId') and parent is None:raise ValueError('领域的上级空间不存在')
        parent=parent or science_root(state,create=True)
        if parent.get('module'):raise ValueError('功能模块不能作为领域的上级空间')
        if parent['name']=='中科院':a['scienceRootId']=parent['id']
        f=child_folder(state,parent,c.get('name'))
    if f.get('module'):raise ValueError('功能模块不能作为领域资料夹')
    existing=next((d for d in a['domains'] if d.get('folderId')==f['id']),None)
    if existing:
        if existing['archived']:raise ValueError('这个资料夹已关联收起的领域，请在领域设置中恢复')
        return existing
    id=f['id'] if not any(d['id']==f['id'] for d in a['domains']) else str(uuid.uuid4())
    d={'id':id,'folderId':f['id'],'name':f['name'],'goal':'','focusId':None,'archived':False}
    a['domains'].append(d);return d


def rename_domain(state,d,name):
    name=text(name,80,True).strip();f=next((f for f in state['folders'] if f['id']==d.get('folderId')),None)
    if f:
        if any(x['id']!=f['id'] and x.get('parent')==f.get('parent') and x['name']==name for x in state['folders']):raise ValueError('此位置已有同名文件夹')
        f['name']=name
    d['name']=name


def synchronize(state):
    a=state.get('advancement')
    if a is None:return
    root=science_root(state);folders={f['id']:f for f in state['folders']}
    for d in a['domains']:
        f=folders.get(d.get('folderId'))
        if root and f and f['id']==root['id'] and d['name']!=root['name']:
            child=child_folder(state,root,d['name'])
            if any(x['id']!=d['id'] and x.get('folderId')==child['id'] for x in a['domains']):raise ValueError('同名领域已有关联，请先确认，旧记录不会合并')
            d['folderId']=child['id'];f=child;folders[f['id']]=f
        if f:d['name']=f['name']
    if root:
        linked={d.get('folderId') for d in a['domains']}
        ids={d['id'] for d in a['domains']}
        for f in state['folders']:
            if f.get('parent')!=root['id'] or f.get('module') or f['id'] in linked:continue
            id=f['id'] if f['id'] not in ids else str(uuid.uuid4());ids.add(id);linked.add(f['id'])
            a['domains'].append({'id':id,'folderId':f['id'],'name':f['name'],'goal':'','focusId':None,'archived':False})
