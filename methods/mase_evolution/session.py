"""MASE逐调用审计：只保存引用、成本与脱敏诊断，不保存原始提示词或隐藏推理。"""
import hashlib
import uuid
from methods.a7_exploration.workflow import Session as BaseSession


class Session(BaseSession):
    """解题/设计/公开检查共用调用记录；来源长期库只读，失败不伪造已知token成本。"""
    def __init__(self,requesters):
        audited={}
        for capacity,request in requesters.items():
            def wrapper(prompt,request=request):
                response=request(prompt)
                self._response_usage=dict(response.get('usage') or {})
                return response
            audited[capacity]=wrapper
        super().__init__(audited)

    def ask(self,prompt,stage,budget=4096):
        """输入模板和公开引用→模型输出；各尝试独立ID/输入哈希/usage，异常由底层脱敏。"""
        first=len(self.trace)
        self._response_usage=None
        try:
            return super().ask(prompt,stage,budget)
        finally:
            for event in self.trace[first:]:
                event['call_id']=uuid.uuid4().hex
                event['input_sha256']=hashlib.sha256(prompt.encode()).hexdigest()
                # 底层失败不一定返回计费信息，保留unknown；不可把未获知成本记成0。
                event['usage']=None if event.get('error_type') else self._response_usage
                event['usage_status']='reported' if event['usage'] is not None else 'unknown'
