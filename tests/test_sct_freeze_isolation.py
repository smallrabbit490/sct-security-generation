from methods.sct_agent.experience_lifecycle import can_update_memory
from methods.sct_agent.schemas import FreezeManifest


def test_frozen_evaluation_rejects_memory_updates():
    manifest = FreezeManifest(model="test", memory_sha256="abc", feedback_channel="disabled")
    assert can_update_memory(manifest) is False

