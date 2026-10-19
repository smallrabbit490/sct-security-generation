"""资格回放只移除既有奖励，不把缺测变成失败或把排名当代码结果。"""
from configs.cle_q_pro_closeout_20261019.replay_qualification import replay
from methods.sct_trajectory.hsk_tree import SecurityInvariantNode
import pytest


def test_replay_excludes_bad_rewards_and_preserves_missing_and_source():
    nodes = [SecurityInvariantNode.from_dict({'invariant_id': 'a', 'q_value': .9, 'q_visits': 99})]
    events = [{'task_id': '1', 'invariant_id': 'a', 'reward': 1},
              {'task_id': '2', 'invariant_id': 'a', 'reward': -1},
              {'task_id': '3', 'invariant_id': 'a', 'reward': None}]
    unfiltered, used, removed = replay(nodes, events)
    assert unfiltered[0].q_value == pytest.approx(-.09) and unfiltered[0].q_visits == 2
    screened, used, removed = replay(nodes, events, {'1', '3'})
    assert screened[0].q_value == .3 and screened[0].q_visits == 1
    assert len(used) == len(removed) == 1
    assert nodes[0].q_value == .9 and nodes[0].q_visits == 99
