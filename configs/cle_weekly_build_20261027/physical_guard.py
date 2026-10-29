"""Reuse the established time, budget and wire guard for native CLE builds.

The caller must supply a frozen finite budget and wrap logical model/embedding
requests with wait_allowed; this module does not launch the experiment.
"""
from configs.cle_v41_relation_20261026.execution import StudyExecution


def physical_guard(output, budget, physical_open, *, now=None, wait=None,
                   resume_sources=(), live=False):
    protocol = {
        'paid_execution_enabled': live,
        'planned_P7': 0,
        'budget_proposed': budget,
    }
    kwargs = {'now': now} if now is not None else {}
    if wait is not None:
        kwargs['wait'] = wait
    return StudyExecution(output, protocol, [], client_factory=lambda _: None,
                          physical_open=physical_open, live=live,
                          fixed_eight=False, resume_sources=resume_sources, **kwargs)
