"""Optional planning metadata; legacy task.date keeps its original meaning."""
import datetime as dt
import re

def valid_day(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value) or not '1901-01-01'<=value<='2099-12-31':raise ValueError('任务日期无效')
    dt.date.fromisoformat(value)
    return value

def validate_task(task):
    if not isinstance(task.get('title'),str) or not task['title'].strip() or ('schedule' in task and len(task['title'])>200) or type(task.get('done')) is not bool:raise ValueError('任务格式错误')
    schedule=task.get('schedule','day')
    if schedule not in ('day','recent','deadline'):raise ValueError('任务安排方式无效')
    if schedule=='day':
        if 'schedule' in task:valid_day(task.get('date'))
        else:dt.date.fromisoformat(task['date'])
    elif task.get('date') is not None:raise ValueError('近期或截止任务不指定安排日期')
    deadline=task.get('deadline')
    if schedule=='deadline':valid_day(deadline)
    elif deadline is not None:raise ValueError('此任务不使用截止日期')
    clock=task.get('deadlineTime')
    if clock is not None and (schedule!='deadline' or not isinstance(clock,str) or not re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d',clock)):raise ValueError('截止时间无效')
    if task.get('completedDate') is not None:valid_day(task['completedDate'])
