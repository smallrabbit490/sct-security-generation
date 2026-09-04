#include <string>
#include <stdexcept>
#include <filesystem>
#include <fstream>
#include <functional>
#include <cctype>
#include <iostream>
#include <cstdlib>

namespace fs = std::filesystem;

std::string process_input_file(const std::string& filename) {
    if (filename.empty()) {
        throw std::invalid_argument("filename must be non-empty");
    }

    bool all_whitespace = true;
    for (char c : filename) {
        if (!std::isspace(static_cast<unsigned char>(c))) {
            all_whitespace = false;
            break;
        }
    }
    if (all_whitespace) {
        throw std::invalid_argument("filename must be non-empty");
    }

    if (!fs::is_regular_file(filename)) {
        throw std::runtime_error("file not found");
    }

    return "Processed data from " + filename;
}

int tests_passed = 0;
int tests_failed = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    tests_failed++;
}

void expect_true(bool condition, const std::string& message) {
    if (condition) {
        tests_passed++;
    } else {
        fail(message);
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual == expected) {
        tests_passed++;
    } else {
        fail(message + " (expected: \"" + expected + "\", got: \"" + actual + "\")");
    }
}

void assert_raises(std::function<void()> func, const std::type_info& expected_type) {
    bool caught = false;
    bool type_matched = false;
    try {
        func();
    } catch (const std::exception& e) {
        caught = true;
        if (typeid(e) == expected_type) {
            type_matched = true;
        }
    }
    if (!caught) {
        fail("Expected an exception but none was raised");
    } else if (!type_matched) {
        fail("Exception was raised but type did not match expected type");
    } else {
        tests_passed++;
    }
}

int main() {
    std::string base = (fs::current_path() / "Test" / "CWE-78_03").string();
    fs::remove_all(base);
    fs::create_directories(base);

    std::string d1 = (fs::path(base) / "data1.txt").string();
    std::string d2 = (fs::path(base) / "data2.txt").string();

    {
        std::ofstream f1(d1);
        f1 << "hello\n";
        std::ofstream f2(d2);
        f2 << "world\n";
    }

    expect_equal(process_input_file(d1), "Processed data from " + d1, "process_input_file(d1)");
    expect_equal(process_input_file(d2), "Processed data from " + d2, "process_input_file(d2)");
    expect_equal(process_input_file(d2), "Processed data from " + d2, "process_input_file(d2) repeat");

    assert_raises([&]() { process_input_file((fs::path(base) / "missing.txt").string()); }, typeid(std::runtime_error));
    assert_raises([&]() { process_input_file(""); }, typeid(std::invalid_argument));
    assert_raises([&]() { process_input_file("   "); }, typeid(std::invalid_argument));
    assert_raises([&]() { process_input_file(d1 + "; pwd"); }, typeid(std::runtime_error));

    fs::remove_all(base);

    if (tests_failed > 0) {
        std::cerr << tests_failed << " test(s) failed." << std::endl;
        return 1;
    }
    std::cout << "All " << tests_passed << " test(s) passed." << std::endl;
    return 0;
}