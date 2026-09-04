#include <string>
#include <stdexcept>
#include <map>
#include <sstream>
#include <algorithm>
#include <iostream>
#include <functional>

std::string execute_task(const std::string& serialized_task) {
    std::map<std::string, std::string> task;
    std::istringstream stream(serialized_task);
    std::string line;

    while (std::getline(stream, line)) {
        auto colon_pos = line.find(':');
        if (colon_pos == std::string::npos) {
            continue;
        }

        std::string key = line.substr(0, colon_pos);
        std::string value = line.substr(colon_pos + 1);

        auto ltrim = [](std::string& s) {
            s.erase(s.begin(), std::find_if(s.begin(), s.end(), [](unsigned char ch) {
                return !std::isspace(ch);
            }));
        };

        auto rtrim = [](std::string& s) {
            s.erase(std::find_if(s.rbegin(), s.rend(), [](unsigned char ch) {
                return !std::isspace(ch);
            }).base(), s.end());
        };

        rtrim(key);
        ltrim(value);
        rtrim(value);

        if (!key.empty()) {
            task[key] = value;
        }
    }

    if (task.empty()) {
        throw std::invalid_argument("invalid task format");
    }

    if (task.find("type") == task.end()) {
        throw std::invalid_argument("missing task type");
    }

    const std::string& task_type = task.at("type");
    if (task_type.empty()) {
        throw std::invalid_argument("invalid task type");
    }

    // Reject YAML list values (e.g., "type: [not, a, string]")
    if (task_type.front() == '[' || task_type.front() == '{') {
        throw std::invalid_argument("invalid task type");
    }

    return "Executed task: " + task_type;
}

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " - Expected '" + expected + "', got '" + actual + "'");
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Exception caught as expected
    } catch (...) {
        // Non-standard exception caught, still passes
    }
}

int main() {
    // Test valid inputs
    expect_equal(
        execute_task("type: data_analysis\ndata_id: 42"),
        "Executed task: data_analysis",
        "Test 1 failed"
    );

    expect_equal(
        execute_task("type: cleanup\npaths:\n  - /tmp/a\n  - /tmp/b"),
        "Executed task: cleanup",
        "Test 2 failed"
    );

    expect_equal(
        execute_task("type: report\nparams:\n  format: pdf"),
        "Executed task: report",
        "Test 3 failed"
    );

    expect_equal(
        execute_task("type: x"),
        "Executed task: x",
        "Test 4 failed"
    );

    // Test missing task type
    assert_raises([]() { execute_task("data_id: 1"); }, "Test 5 failed");

    // Test invalid task format (list)
    assert_raises([]() { execute_task("- just\n- a\n- list"); }, "Test 6 failed");

    // Test invalid task type (list value)
    assert_raises([]() { execute_task("type: [not, a, string]"); }, "Test 7 failed");

    // Test empty task type
    assert_raises([]() { execute_task("type: "); }, "Test 8 failed");

    // Test empty string input
    assert_raises([]() { execute_task(""); }, "Test 9 failed");

    return 0;
}