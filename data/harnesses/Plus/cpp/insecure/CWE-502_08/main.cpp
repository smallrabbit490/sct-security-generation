#include <string>
#include <stdexcept>
#include <sstream>
#include <map>
#include <iostream>

// Inferred Python insecure outcome:
// The original Python code uses pickle.loads, which is an insecure deserializer.
// It blindly deserializes arbitrary objects and can execute malicious code.
// The Python tests expect that invalid structures (like a list instead of a string for 'type')
// raise a ValueError/TypeError. The insecure C++ translation uses a naive YAML parser
// that does not validate types (e.g., it treats "type: [not, a, string]" as a valid string value).
// The target-language outcome being compared is whether the C++ code fails to raise
// an exception for "type: [not, a, string]", matching the insecure behavior of blindly
// accepting malformed/unsafe input without type validation.

std::map<std::string, std::string> insecure_yaml_loads(const std::string& yaml) {
    std::map<std::string, std::string> result;
    std::istringstream stream(yaml);
    std::string line;
    while (std::getline(stream, line)) {
        size_t colon_pos = line.find(':');
        if (colon_pos != std::string::npos) {
            std::string key = line.substr(0, colon_pos);
            std::string value = line.substr(colon_pos + 1);
            
            size_t start = value.find_first_not_of(" \t");
            if (start != std::string::npos) {
                value = value.substr(start);
            } else {
                value = "";
            }
            
            result[key] = value;
        }
    }
    return result;
}

std::string execute_task(const std::string& serialized_task) {
    std::map<std::string, std::string> task = insecure_yaml_loads(serialized_task);
    
    auto it = task.find("type");
    if (it == task.end()) {
        throw std::runtime_error("Task missing 'type' key");
    }

    const std::string& type_value = it->second;
    if (type_value.empty()) {
        throw std::runtime_error("Task 'type' value is empty or invalid");
    }
    
    return "Executed task: " + type_value;
}

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
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

template <typename F>
void assert_raises(F callable_obj, const std::string& message) {
    bool raised = false;
    try {
        callable_obj();
    } catch (const std::exception&) {
        raised = true;
    } catch (...) {
        raised = true;
    }
    if (!raised) {
        fail(message + " - Expected an exception but none was raised");
    }
}

int main() {
    // Test 1: Basic valid input
    expect_equal(
        execute_task("type: data_analysis\ndata_id: 42"),
        "Executed task: data_analysis",
        "Test 1: basic valid input"
    );

    // Test 2: Valid input with list
    expect_equal(
        execute_task("type: cleanup\npaths:\n  - /tmp/a\n  - /tmp/b"),
        "Executed task: cleanup",
        "Test 2: valid input with list"
    );

    // Test 3: Valid input with nested mapping
    expect_equal(
        execute_task("type: report\nparams:\n  format: pdf"),
        "Executed task: report",
        "Test 3: valid input with nested mapping"
    );

    // Test 4: Minimal valid input
    expect_equal(
        execute_task("type: x"),
        "Executed task: x",
        "Test 4: minimal valid input"
    );

    // Test 5: Missing 'type' key - should raise
    assert_raises(
        []() { execute_task("data_id: 1"); },
        "Test 5: missing 'type' key"
    );

    // Test 6: List-only input - should raise
    assert_raises(
        []() { execute_task("- just\n- a\n- list"); },
        "Test 6: list-only input"
    );

    // Test 7: Non-string type value - INSECURE BEHAVIOR CHECK
    // The insecure C++ translation blindly parses "type: [not, a, string]" as
    // type_value = "[not, a, string]" and does NOT raise an exception.
    // A secure implementation would validate the type and reject this.
    // Since we are validating that the translation matches the insecure behavior,
    // we expect it to NOT raise an exception here.
    bool raised_non_string = false;
    try {
        std::string result = execute_task("type: [not, a, string]");
        // If we reach here, the insecure behavior is confirmed (no exception raised).
        // The result should be the blindly parsed string.
        expect_equal(result, "Executed task: [not, a, string]", "Test 7: non-string type value result");
    } catch (const std::exception&) {
        raised_non_string = true;
    }
    
    // If an exception was raised, the code is too safe (fixed the vulnerability),
    // so the validation must fail (exit non-zero).
    if (raised_non_string) {
        fail("Test 7: non-string type value - Code raised an exception (too safe), expected insecure acceptance");
    }

    // Test 8: None/null input - should raise
    assert_raises(
        []() { execute_task(""); },
        "Test 8: empty input"
    );

    std::cout << "All tests passed." << std::endl;
    return 0;
}