from methods.sct_agent.failure_clustering import cluster_failures


def test_failure_cluster_redacts_task_and_test_values():
    clusters = cluster_failures(
        [{"task_id": "secret-1", "stderr": "assert token=abc", "error_type": "security"}],
        min_support=1,
    )
    payload = clusters[0].to_dict()
    assert "secret-1" not in str(payload)
    assert "abc" not in str(payload)

