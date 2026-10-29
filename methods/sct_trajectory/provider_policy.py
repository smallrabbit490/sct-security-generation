"""当前CLE模型与用户指定的低谷调用时段；不调API、不改变历史请求的模型名。"""
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo


CURRENT_MODEL = 'deepseek-v4.1-flash-1017'
MODEL_REVISION = 'ds41flash1017-offpeak-v1'
SHANGHAI = ZoneInfo('Asia/Shanghai')


class ModelTimeWindowError(RuntimeError):
    """当前模型处在用户禁止的时段，必须在发送HTTP之前停止。"""


def ensure_model_call_allowed(model, now=None):
    """按北京时间检查每次实际派发；只限制本次指定模型，不等待或重试到别的时段。"""
    if model != CURRENT_MODEL:
        return
    local = (now or datetime.now(timezone.utc)).astimezone(SHANGHAI)
    clock = local.time()
    if local.weekday() < 5 and (time(9) <= clock < time(12) or time(14) <= clock < time(18)):
        raise ModelTimeWindowError(
            'model_call_blocked_by_user_schedule: deepseek-v4.1-flash-1017; '
            'Asia/Shanghai weekdays 09:00-12:00 and 14:00-18:00 prohibited')
