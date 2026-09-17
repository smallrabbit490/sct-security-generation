from methods.sct_agent.difference_analysis import analyze_difference


def test_path_patch_extracts_six_required_categories():
    result = analyze_difference(
        "open(user_path)",
        "open(root / safe_name)",
        {"arguments": "user_path", "description": "读取用户提供的文件"},
        "22",
    )
    assert "user_path" in result.untrusted_inputs
    assert result.sensitive_operations
    assert result.trigger_conditions
    assert result.patch_changes
    assert result.postconditions
    assert result.dangerous_patterns

