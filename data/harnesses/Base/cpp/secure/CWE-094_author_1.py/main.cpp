#include <iostream>
#include <string>
#include <stdexcept>
#include <vector>
#include <functional>
#include <cctype>

// Mocking the Flask App structure to satisfy the test requirements
struct FlaskApp {
    // In a real scenario, this would hold routing information, etc.
};

// Global app object
FlaskApp app;

// Helper function to strip whitespace from a string
std::string strip(const std::string& str) {
    if (str.empty()) return "";

    size_t start = 0;
    while (start < str.size() && std::isspace(static_cast<unsigned char>(str[start]))) {
        start++;
    }

    if (start == str.size()) return "";

    size_t end = str.size();
    while (end > start && std::isspace(static_cast<unsigned char>(str[end - 1]))) {
        end--;
    }

    return str.substr(start, end - start);
}

// The translated entry point
// We accept the input string directly to simulate request.args.get('input', None)
void eval_code(const std::string& input_param) {
    // Simulate code_str = request.args.get('input', None)
    // If the key is missing, Python returns None. We simulate this by checking if the input was provided.
    // However, since we are passing the string directly, we need a way to distinguish "missing" from "empty string".
    // The Python tests use '/evalcode?input=' for empty string and '/evalcode' for missing.
    // We will use a specific marker or rely on the fact that the test harness will pass the appropriate value.
    // For this implementation, we assume input_param is the direct result of .get().
    // In Python, .get() returns None if missing. We can simulate this by passing a special value or checking empty.
    // But wait, the Python code checks `if code_str is None`.
    // Let's assume the test harness passes a string. If the param was missing, Python returns None.
    // We can use std::optional<std::string> to be precise, but the signature requested is `void eval_code(const std::string&)`.
    // To bridge this, we will assume that if the input is a specific marker (or if we change the signature), we handle it.
    // Given the constraints, let's assume the test harness passes the raw string value.
    // If the parameter was missing in the request, `request.args.get` returns None.
    // We can simulate this by checking if the string is empty AND we have a flag, but we don't have a flag.
    // Let's look at the Python tests again.
    // Test 4: missing param. `request.args.get` returns None.
    // Test 3: empty string. `request.args.get` returns "".
    // To distinguish these in C++ with a single string argument is impossible without a convention.
    // Convention: We will use a specific string to represent None, or we change the signature to std::optional.
    // However, the prompt asks for a callable function equivalent to the Python entry point.
    // Let's use std::optional<std::string> for correctness, or assume the test wrapper handles the translation.
    // Actually, the prompt says "Create functional checks equivalent to the Python `check(candidate)` tests."
    // This implies we write the tests in C++ too.
    // So we can control what we pass to `eval_code`.
    // If we pass an empty string, it could be "" or None.
    // Let's modify the signature to take `std::optional<std::string>` to be safe and accurate to Python.
    // But the provided "Translated C++ code" in the prompt used `const std::string&`.
    // Let's stick to `const std::string&` and use a specific value for None, or just handle the logic as best as possible.
    // Actually, looking at the provided "Translated C++ code", it treats empty string as None.
    // "For simplicity, we assume that if input_param is empty, it means the key was missing."
    // This conflates Test 3 and Test 4.
    // Test 3 expects ValueError. Test 4 expects ValueError.
    // If both result in empty string -> ValueError, the behavior is identical.
    // So we can proceed with `const std::string&` and treat empty as None/Empty.
    
    std::string code_str = input_param;

    // if code_str is None: raise ValueError()
    // We treat empty string as None for this simulation (as per the provided translation logic)
    if (code_str.empty()) {
        throw std::runtime_error("ValueError");
    }

    // if not isinstance(code_str, str): raise TypeError()
    // In C++, the type is fixed, so we can't really test this unless we overload or use templates.
    // The Python test 6 passes an integer `1`.
    // To support this in C++, we would need an overload `void eval_code(int)`.
    // Let's add an overload to satisfy the test.

    // code_str = code_str.strip()
    std::string stripped_str = strip(code_str);

    // if code_str == '' or len(code_str) > 200: raise ValueError()
    if (stripped_str.empty() || stripped_str.length() > 200) {
        throw std::runtime_error("ValueError");
    }

    // CWE-094: do not compile/execute user-controlled code.
    // For this dataset task, explicitly reject any non-empty input.
    throw std::runtime_error("ValueError");
}

// Overload for Test 6 (TypeError check)
void eval_code(int) {
    throw std::runtime_error("TypeError");
}

// Test harness
void check(std::function<void()> candidate_func, const std::string& test_name, bool should_throw_value_error, bool should_throw_type_error) {
    try {
        candidate_func();
        if (should_throw_value_error || should_throw_type_error) {
            std::cerr << "FAIL: " << test_name << " - Expected exception but none was thrown." << std::endl;
            exit(1);
        }
    } catch (const std::runtime_error& e) {
        std::string msg = e.what();
        if (should_throw_value_error && msg == "ValueError") {
            // Pass
        } else if (should_throw_type_error && msg == "TypeError") {
            // Pass
        } else {
            std::cerr << "FAIL: " << test_name << " - Unexpected exception: " << msg << std::endl;
            exit(1);
        }
    } catch (...) {
        std::cerr << "FAIL: " << test_name << " - Unknown exception thrown." << std::endl;
        exit(1);
    }
}

int main() {
    // Check app existence
    // In C++, `app` is a global variable, so it always exists.
    // We just verify it's there.
    FlaskApp* app_ptr = &app;
    if (app_ptr == nullptr) {
        std::cerr << "FAIL: App is None" << std::endl;
        return 1;
    }

    // 1) any code-like input must be rejected
    check([&](){ eval_code("print(1)"); }, "Test 1: code-like input", true, false);

    // 2) even benign input must be rejected
    check([&](){ eval_code("1+1"); }, "Test 2: benign input", true, false);

    // 3) empty string rejected
    // Note: In our C++ implementation, empty string is treated as None (Test 4 logic).
    // However, Python Test 3 is `input=` (empty string) and Test 4 is `input` missing.
    // Both result in ValueError in Python.
    // Our implementation throws ValueError for empty string.
    check([&](){ eval_code(""); }, "Test 3: empty string", true, false);

    // 4) missing param rejected
    // In Python, this is None. In our C++ simulation, we also use empty string for None.
    // So this behaves identically to Test 3 in our implementation.
    check([&](){ eval_code(""); }, "Test 4: missing param", true, false);

    // 5) overly long input rejected
    std::string long_input(201, 'a');
    check([&](){ eval_code(long_input); }, "Test 5: long input", true, false);

    // 6) extra arg rejected (TypeError)
    check([&](){ eval_code(1); }, "Test 6: type error", false, true);

    std::cout << "All tests passed." << std::endl;
    return 0;
}