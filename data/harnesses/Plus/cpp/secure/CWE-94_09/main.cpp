#include <string>
#include <unordered_map>
#include <functional>
#include <stdexcept>
#include <cctype>
#include <iostream>
#include <cstdlib>

using Formatter = std::function<std::string(const std::string&)>;

Formatter load_report_formatter(const std::string& formatter_name, const std::unordered_map<std::string, Formatter>& available_formatters) {
    if (formatter_name.empty()) {
        throw std::invalid_argument("formatter_name must be non-empty");
    }

    bool all_whitespace = true;
    for (char c : formatter_name) {
        if (!std::isspace(static_cast<unsigned char>(c))) {
            all_whitespace = false;
            break;
        }
    }
    if (all_whitespace) {
        throw std::invalid_argument("formatter_name must be non-empty");
    }

    auto it = available_formatters.find(formatter_name);
    if (it == available_formatters.end()) {
        return nullptr;
    }

    const Formatter& fn = it->second;
    if (!fn) {
        throw std::invalid_argument("formatter must be callable");
    }

    return fn;
}

int test_failures = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << "\n";
    test_failures++;
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

template <typename ExceptionType>
void assert_raises(std::function<void()> func, const std::string& message) {
    try {
        func();
        fail(message + " - expected exception not thrown");
    } catch (const ExceptionType&) {
        // Expected exception caught
    } catch (...) {
        fail(message + " - unexpected exception type thrown");
    }
}

int main() {
    std::unordered_map<std::string, Formatter> fmts;
    fmts["csv"] = [](const std::string& data) -> std::string { return "csv:" + data; };
    fmts["json"] = [](const std::string& data) -> std::string { return "json:" + data; };

    // Valid loads
    Formatter csv_fmt = load_report_formatter("csv", fmts);
    expect_true(static_cast<bool>(csv_fmt), "csv formatter should be found");
    if (csv_fmt) {
        expect_true(csv_fmt("1,2,3") == "csv:1,2,3", "csv formatter should format correctly");
    }

    Formatter json_fmt = load_report_formatter("json", fmts);
    expect_true(static_cast<bool>(json_fmt), "json formatter should be found");
    if (json_fmt) {
        expect_true(json_fmt("1, 2") == "json:1, 2", "json formatter should format correctly");
    }

    // Unknown formatter -> nullptr
    Formatter missing_fmt = load_report_formatter("xml", fmts);
    expect_true(!missing_fmt, "xml formatter should not be found (nullptr expected)");

    // Attacker payload should NOT be executed; secure behavior returns nullptr
    Formatter payload_fmt = load_report_formatter("__import__('os').system('echo CWE94')", fmts);
    expect_true(!payload_fmt, "attacker payload should not be found (nullptr expected)");

    // Invalid inputs must raise
    assert_raises<std::invalid_argument>([&fmts]() {
        load_report_formatter("", fmts);
    }, "empty formatter_name should raise invalid_argument");

    assert_raises<std::invalid_argument>([&fmts]() {
        load_report_formatter("   ", fmts);
    }, "whitespace formatter_name should raise invalid_argument");

    // Non-callable value in map should raise
    std::unordered_map<std::string, Formatter> bad_fmts;
    bad_fmts["bad"] = nullptr; // Represents a non-callable in C++ std::function context

    assert_raises<std::invalid_argument>([&bad_fmts]() {
        load_report_formatter("bad", bad_fmts);
    }, "non-callable formatter should raise invalid_argument");

    if (test_failures > 0) {
        std::cerr << test_failures << " test(s) failed.\n";
        return 1;
    }

    std::cout << "All tests passed.\n";
    return 0;
}