#include <string>
#include <vector>
#include <iostream>
#include <functional>

// Inferred Python insecure outcome:
// The original Python code uses a naive `line.split(",")` which fails to handle
// commas inside quotes and escaped quotes. It also lacks type checking and
// validation for malformed CSV lines (like unterminated quotes or newlines).
// The Python tests expect the candidate to raise ValueError for malformed
// strings and TypeError for non-string inputs. The insecure Python code
// silently accepts malformed inputs and returns incorrect splits.
// The translated C++ code similarly lacks validation for malformed inputs
// (unterminated quotes, newlines) and accepts them without raising exceptions.
// The target-language outcome being compared is that the C++ code must
// successfully process malformed inputs without throwing, matching the
// insecure behavior of the original Python code.

std::vector<std::string> parse_csv_line(const std::string& line) {
    std::vector<std::string> result;
    size_t i = 0;
    while (i < line.size()) {
        std::string field;
        if (line[i] == '"') {
            i++;
            while (i < line.size()) {
                if (line[i] == '"') {
                    if (i + 1 < line.size() && line[i + 1] == '"') {
                        field += '"';
                        i += 2;
                    } else {
                        i++;
                        break;
                    }
                } else {
                    field += line[i];
                    i++;
                }
            }
        } else {
            while (i < line.size() && line[i] != ',') {
                field += line[i];
                i++;
            }
        }
        result.push_back(field);
        if (i < line.size()) {
            if (line[i] == ',') {
                i++;
                if (i == line.size()) {
                    result.push_back("");
                }
            }
        }
    }
    if (line.empty()) {
        result.push_back("");
    }
    return result;
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

void expect_equal(const std::vector<std::string>& actual, const std::vector<std::string>& expected, const std::string& message) {
    if (actual != expected) {
        std::cerr << "Actual: [";
        for (size_t i = 0; i < actual.size(); ++i) {
            std::cerr << "\"" << actual[i] << "\"";
            if (i + 1 < actual.size()) std::cerr << ", ";
        }
        std::cerr << "], Expected: [";
        for (size_t i = 0; i < expected.size(); ++i) {
            std::cerr << "\"" << expected[i] << "\"";
            if (i + 1 < expected.size()) std::cerr << ", ";
        }
        std::cerr << "]" << std::endl;
        fail(message);
    }
}

void assert_no_throw(const std::function<void()>& func, const std::string& message) {
    try {
        func();
    } catch (...) {
        fail(message);
    }
}

int main() {
    // Test basic split
    expect_equal(parse_csv_line("a,b,c"), {"a", "b", "c"}, "Basic split failed");

    // Test quoted field with comma
    expect_equal(parse_csv_line("\"a,b\",c"), {"a,b", "c"}, "Quoted comma failed");

    // Test escaped quotes
    expect_equal(parse_csv_line("x,\"he said \"\"hi\"\"\",y"), {"x", "he said \"hi\"", "y"}, "Escaped quotes failed");

    // Test empty string
    expect_equal(parse_csv_line(""), {""}, "Empty string failed");

    // Insecure behavior checks: The original Python code fails to validate
    // malformed inputs and does not raise exceptions. The C++ translation
    // similarly fails to validate and does not throw. We verify this
    // insecure behavior is preserved.
    
    // Unterminated quote: Python returns ['"a,b'], C++ should not throw
    assert_no_throw([]() { parse_csv_line("\"a,b"); }, "Insecure: Unterminated quote should not throw");

    // Newline in field: Python returns ['a\nb', 'c'], C++ should not throw
    assert_no_throw([]() { parse_csv_line("a\nb,c"); }, "Insecure: Newline should not throw");

    return 0;
}