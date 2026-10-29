"""One matched V4.1 P7 cell for empty, existing or newly built memory."""
import copy

from methods.cle_ablation import runner
from methods.cle_ablation.run_memory_view_probe import ViewProvider


def run_cell(task, bank_arm, start, retrieve, request):
    if bank_arm not in ('E0', 'C32', 'C41'):
        raise ValueError('unknown_cross_memory_arm')
    required = ('query', 'selected_cards', 'retrieval_trace', 'initial_analysis')
    if any(key not in start for key in required):
        raise ValueError('cross_shared_start_incomplete')
    if len(start['selected_cards']) > 3:
        raise ValueError('original_CLE_card_cap_exceeded')
    mode = 'B0' if bank_arm == 'E0' else 'BM'
    # BM preserves the original card fields; material decomposition is not
    # consulted for this view. Each non-empty bank supplies its own selection.
    provider = ViewProvider(copy.deepcopy(start), mode, retrieve, lambda cards: {})
    return runner.run_one('PLT', task, 'P7', request, {'full': []},
                          initial_analysis=copy.deepcopy(start['initial_analysis']),
                          retrieval_provider=provider, max_experiences=3)
