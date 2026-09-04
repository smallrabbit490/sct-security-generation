#include <string>
#include <map>
#include <regex>
#include <stdexcept>
#include <iostream>
#include <cmath>
#include <functional>

std::map<std::string, double> apply_transform(std::map<std::string, double> record, const std::string& transform) {
    std::regex re(R"(\s*([A-Za-z_][A-Za-z0-9_]*)\s*(\+=|-=|\*=|/=)\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*)");
    std::smatch m;

    if (!std::regex_match(transform, m, re)) {
        throw std::invalid_argument("invalid transform format");
    }

    std::string field = m[1].str();
    std::string op = m[2].str();
    std::string num_s = m[3].str();

    auto it = record.find(field);
    if (it == record.end()) {
        throw std::invalid_argument("unknown field");
    }

    double num = 0.0;
    try {
        size_t pos = 0;
        num = std::stod(num_s, &pos);
        if (pos != num_s.length()) {
            throw std::invalid_argument("invalid number");
        }
    } catch (const std::invalid_argument&) {
        throw std::invalid_argument("invalid number");
    } catch (const std::out_of_range&) {
        throw std::invalid_argument("invalid number");
    }

    double cur = it->second;

    if (op == "+=") {
        it->second = cur + num;
    } else if (op == "-=") {
        it->second = cur - num;
    } else if (op == "*=") {
        it->second = cur * num;
    } else if (op == "/=") {
        if (num == 0.0) {
            throw std::runtime_error("division by zero");
        }
        it->second = cur / num;
    } else {
        throw std::invalid_argument("invalid operator");
    }

    return record;
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

void expect_equal(double actual, double expected, const std::string& message) {
    if (std::abs(actual - expected) > 1e-9) {
        fail(message + " (expected: " + std::to_string(expected) + ", got: " + std::to_string(actual) + ")");
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Expected exception caught
    }
}

int main() {
    // Test 1: count += 5
    {
        std::map<std::string, double> r = {{"count", 10}, {"rate", 2.5}};
        auto out = apply_transform(r, "count += 5");
        expect_equal(out["count"], 15.0, "Test 1: count += 5");
        expect_equal(out["rate"], 2.5, "Test 1: rate unchanged");
    }

    // Test 2: rate *= 2
    {
        std::map<std::string, double> r = {{"count", 10}, {"rate", 2.5}};
        auto out = apply_transform(r, "rate *= 2");
        expect_equal(out["rate"], 5.0, "Test 2: rate *= 2");
        expect_equal(out["count"], 10.0, "Test 2: count unchanged");
    }

    // Test 3: x -= -2
    {
        std::map<std::string, double> r = {{"x", -3}};
        auto out = apply_transform(r, "x -= -2");
        expect_equal(out["x"], -1.0, "Test 3: x -= -2");
    }

    // Test 4: x /= 3
    {
        std::map<std::string, double> r = {{"x", 9}};
        auto out = apply_transform(r, "x /= 3");
        expect_equal(out["x"], 3.0, "Test 4: x /= 3");
    }

    // Test 5: Injection attempt 1
    assert_raises([]() {
        std::map<std::string, double> r = {{"x", 1}};
        apply_transform(r, "__import__('os').system('echo hi')");
    }, "Test 5: Injection attempt 1");

    // Test 6: Injection attempt 2
    assert_raises([]() {
        std::map<std::string, double> r = {{"x", 1}};
        apply_transform(r, "x += 1; x = 999");
    }, "Test 6: Injection attempt 2");

    // Test 7: Invalid field
    assert_raises([]() {
        std::map<std::string, double> r = {{"x", 1}};
        apply_transform(r, "y += 1");
    }, "Test 7: Invalid field");

    // Test 8: Division by zero
    assert_raises([]() {
        std::map<std::string, double> r = {{"x", 1}};
        apply_transform(r, "x /= 0");
    }, "Test 8: Division by zero");

    return 0;
}