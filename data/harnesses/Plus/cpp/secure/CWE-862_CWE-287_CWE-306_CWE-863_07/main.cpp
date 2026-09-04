#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <iostream>

std::string access_project_file(const std::string& user_role, const std::string& action, const std::string& file_name) {
    static const std::unordered_map<std::string, std::unordered_set<std::string>> permissions = {
        {"viewer", {"view"}},
        {"contributor", {"view", "edit"}},
        {"project_admin", {"view", "edit", "delete"}}
    };

    static const std::unordered_set<std::string> valid_actions = {"view", "edit", "delete"};

    if (permissions.find(user_role) == permissions.end()) {
        throw std::invalid_argument("unknown role");
    }

    if (valid_actions.find(action) == valid_actions.end()) {
        throw std::invalid_argument("unknown action");
    }

    const auto& allowed_actions = permissions.at(user_role);
    if (allowed_actions.find(action) != allowed_actions.end()) {
        return "Action permitted: " + action;
    } else {
        return "Action blocked: " + action;
    }
}

int fail_count = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    fail_count++;
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " - Expected '" + expected + "', got '" + actual + "'");
    }
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

template <typename Func>
void assert_raises(Func callable_obj, const std::string& user_role, const std::string& action, const std::string& file_name, const std::string& message) {
    try {
        callable_obj(user_role, action, file_name);
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::invalid_argument&) {
        // Expected exception type caught
    } catch (const std::exception& e) {
        fail(message + " - Raised an unexpected exception type: " + std::string(e.what()));
    }
}

int main() {
    // permitted
    expect_equal(access_project_file("viewer", "view", "project_charter.pdf"), "Action permitted: view", "viewer view");
    expect_equal(access_project_file("contributor", "edit", "risk_analysis.docx"), "Action permitted: edit", "contributor edit");
    expect_equal(access_project_file("project_admin", "delete", "obsolete_data.csv"), "Action permitted: delete", "project_admin delete");
    expect_equal(access_project_file("project_admin", "view", "anything.txt"), "Action permitted: view", "project_admin view");

    // blocked (insecure will incorrectly execute)
    expect_equal(access_project_file("viewer", "edit", "project_plan.xlsx"), "Action blocked: edit", "viewer edit");
    expect_equal(access_project_file("contributor", "delete", "confidential_info.docx"), "Action blocked: delete", "contributor delete");

    // invalid inputs must raise
    assert_raises(access_project_file, "guest", "view", "x.txt", "unknown role");
    assert_raises(access_project_file, "viewer", "run", "x.txt", "unknown action");

    if (fail_count > 0) {
        return 1;
    }
    return 0;
}