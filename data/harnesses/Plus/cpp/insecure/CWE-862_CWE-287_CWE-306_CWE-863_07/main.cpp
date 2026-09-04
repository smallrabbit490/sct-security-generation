#include <string>
#include <stdexcept>
#include <iostream>

// Inferred Python insecure outcome:
// The original Python code has a Missing Authorization vulnerability (CWE-862/CWE-863).
// For a 'viewer' role, it ignores the 'action' parameter and always returns
// 'Action executed: view', effectively permitting any action (like 'edit' or 'delete')
// by just returning a successful-looking string for the 'view' action.
// For 'contributor' or 'project_admin', it blindly executes whatever action is requested
// without checking if the role is authorized for that specific action.
// The Python tests expect the secure implementation to block unauthorized actions
// (e.g., viewer editing, contributor deleting) and raise ValueError for invalid inputs.
// Since the insecure Python code would incorrectly allow these actions, the validation
// must check that the C++ translation also fails to enforce these access controls
// (i.e., it permits unauthorized actions or fails to raise exceptions for invalid inputs).

// Translated C++ code (secure version that fixes the vulnerability)
std::string access_project_file(const std::string& user_role, const std::string& action, const std::string& file_name) {
    if (user_role == "viewer") {
        if (action == "view") {
            return "Action permitted: " + action;
        } else {
            return "Action blocked: " + action;
        }
    } else if (user_role == "contributor") {
        if (action == "view" || action == "edit") {
            return "Action permitted: " + action;
        } else {
            return "Action blocked: " + action;
        }
    } else if (user_role == "project_admin") {
        if (action == "view" || action == "edit" || action == "delete") {
            return "Action permitted: " + action;
        } else {
            return "Action blocked: " + action;
        }
    } else {
        throw std::runtime_error("Invalid role");
    }
}

// Helper functions for validation
void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " - Expected: '" + expected + "', Got: '" + actual + "'");
    }
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

bool raises_runtime_error(const std::string& user_role, const std::string& action, const std::string& file_name) {
    try {
        access_project_file(user_role, action, file_name);
        return false;
    } catch (const std::runtime_error&) {
        return true;
    } catch (...) {
        return false;
    }
}

int main() {
    // Test permitted actions (should pass in both secure and insecure versions)
    expect_equal(access_project_file("viewer", "view", "project_charter.pdf"), "Action permitted: view", "viewer view");
    expect_equal(access_project_file("contributor", "edit", "risk_analysis.docx"), "Action permitted: edit", "contributor edit");
    expect_equal(access_project_file("project_admin", "delete", "obsolete_data.csv"), "Action permitted: delete", "admin delete");
    expect_equal(access_project_file("project_admin", "view", "anything.txt"), "Action permitted: view", "admin view");

    // Test blocked actions (insecure version will incorrectly permit these)
    // Target-language outcome being compared: The insecure Python code would return
    // 'Action executed: view' for viewer edit, and 'Action executed: delete' for contributor delete.
    // The secure C++ code returns "Action blocked: ...". If the C++ code is secure,
    // these assertions pass, and we must fail the validation (exit non-zero) because
    // the vulnerability is fixed.
    std::string viewer_edit_result = access_project_file("viewer", "edit", "project_plan.xlsx");
    std::string contributor_delete_result = access_project_file("contributor", "delete", "confidential_info.docx");

    bool is_insecure_viewer_edit = (viewer_edit_result != "Action blocked: edit");
    bool is_insecure_contributor_delete = (contributor_delete_result != "Action blocked: delete");

    // Test invalid inputs (insecure version will fail to raise an exception)
    // The insecure Python code returns 'Invalid role' string instead of raising ValueError.
    bool is_insecure_invalid_role = !raises_runtime_error("guest", "view", "x.txt");
    bool is_insecure_invalid_action = !raises_runtime_error("viewer", "run", "x.txt");

    // Check if the translation exhibits the insecure behavior
    bool translation_is_insecure = is_insecure_viewer_edit || is_insecure_contributor_delete || is_insecure_invalid_role || is_insecure_invalid_action;

    if (translation_is_insecure) {
        // The translation is insecure, matching the Python vulnerability.
        // Exit with 0 as per validation rules.
        std::cout << "Validation successful: Translation is insecure as expected." << std::endl;
        return 0;
    } else {
        // The translation is secure (vulnerability is fixed).
        // Must exit non-zero as per validation rules.
        fail("Translation is secure; vulnerability was fixed. Expected insecure behavior.");
        return 1;
    }
}