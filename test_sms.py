import time
from core.flow_runner import StepContext, StepResult

class FakeCtx(StepContext):
    def __init__(self):
        self.data = {"sms_api_key": "fake_key", "sms_activation_id": "12345"}
        
ctx = FakeCtx()

def _sms_api_call(*args, **kwargs):
    return "STATUS_WAIT_CODE"

from core.flow_runner import StepRegistry
# Create dummy portal
class DummyPortal:
    pass

registry = StepRegistry(DummyPortal())

import core.flow_runner
core.flow_runner._sms_api_call = _sms_api_call

try:
    print("Testing with string timeout...")
    # This will simulate how FlowRunner passes kwargs
    kwargs = {"timeout": "2"}
    registry.execute("sms_get_code", ctx, kwargs)
except Exception as e:
    print("Exception caught:", repr(e))

print("Done")
