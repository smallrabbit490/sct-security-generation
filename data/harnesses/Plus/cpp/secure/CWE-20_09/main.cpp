#include <string>
#include <vector>
#include <stdexcept>
#include <iostream>
#include <functional>

std::vector<std::string> parse_csv_line(const std::string& line) {
    if (line.find('\n') != std::string::npos || line.find('\r') != std::string::npos) {
        throw std::invalid_argument("line must not contain newlines");
    }

    std::vector<std::string> fields;
    std::string buf;
    bool in_quotes = false;
    size_t i = 0;
    size_t n = line.length();

    while (i < n) {
        char ch = line[i];
        if (in_quotes) {
            if (ch == '"') {
                if (i + 1 < n && line[i + 1] == '"') {
                    buf += '"';
                    i += 2;
                    continue;
                }
                in_quotes = false;
                i += 1;
                continue;
            } else {
                buf += ch;
                i += 1;
                continue;
            }
        } else {
            if (ch == '"') {
                in_quotes = true;
                i += 1;
                continue;
            }
            if (ch == ',') {
                fields.push_back(buf);
                buf.clear();
                i += 1;
                continue;
            }
            buf += ch;
            i += 1;
        }
    }

    if (in_quotes) {
        throw std::invalid_argument("unterminated quoted field");
    }

    fields.push_back(buf);
    return fields;
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
        std::string actual_str = "[";
        for (size_t i = 0; i < actual.size(); ++i) {
            actual_str += "\"" + actual[i] + "\"";
            if (i + 1 < actual.size()) actual_str += ", ";
        }
        actual_str += "]";

        std::string expected_str = "[";
        for (size_t i = 0; i < expected.size(); ++i) {
            expected_str += "\"" + expected[i] + "\"";
            if (i + 1 < expected.size()) expected_str += ", ";
        }
        expected_str += "]";

        fail(message + " - Expected " + expected_str + " but got " + actual_str);
    }
}

void assert_raises(const std::function<void()>& callable_obj) {
    try {
        callable_obj();
    } catch (const std::invalid_argument&) {
        return; // Expected exception type caught
    } catch (const std::exception& e) {
        fail(std::string("Raised an unexpected exception type: ") + e.what());
    }
    fail("Expected an exception but none was raised");
}

int main() {
    // Test basic comma separation
    expect_equal(parse_csv_line("a,b,c"), {"a", "b", "c"}, "Basic comma separation");

    // Test quoted field with comma
    expect_equal(parse_csv_line("\"a,b\",c"), {"a,b", "c"}, "Quoted field with comma");

    // Test escaped quotes inside quoted field
    expect_equal(parse_csv_line("x,\"he said \"\"hi\"\"\",y"), {"x", "he said \"hi\"", "y"}, "Escaped quotes");

    // Test empty string
    expect_equal(parse_csv_line(""), {""}, "Empty string");

    // Test unterminated quoted field
    assert_raises([]() { parse_csv_line("\"a,b"); });

    // Test newline in line
    assert_raises([]() { parse_csv_line("a\nb,c"); });

    // Test carriage return in line
    assert_raises([]() { parse_csv_line("a\rb,c"); });

    std::cout << "All tests passed!" << std::endl;
    return 0;
}