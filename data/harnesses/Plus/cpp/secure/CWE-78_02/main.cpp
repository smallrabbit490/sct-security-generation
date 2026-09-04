#include <string>
#include <fstream>
#include <stdexcept>
#include <filesystem>
#include <iostream>
#include <functional>

int count_lines(const std::string& filename) {
    if (filename.empty() || filename.find_first_not_of(" \t\n\r\f\v") == std::string::npos) {
        throw std::invalid_argument("filename must be non-empty");
    }
    if (!std::filesystem::is_regular_file(filename)) {
        throw std::runtime_error("file not found");
    }

    std::ifstream file(filename);
    if (!file.is_open()) {
        throw std::runtime_error("failed to open file");
    }

    int line_count = 0;
    std::string line;
    while (std::getline(file, line)) {
        line_count++;
    }

    return line_count;
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

void expect_equal(int actual, int expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected " + std::to_string(expected) + 
             ", got " + std::to_string(actual) + ")");
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (...) {
        // Exception caught as expected
    }
}

int main() {
    namespace fs = std::filesystem;

    std::string base = "Test/CWE-78_02";
    if (fs::exists(base)) {
        fs::remove_all(base);
    }
    fs::create_directories(base);

    std::string f1 = base + "/example1.txt";
    std::string f2 = base + "/example2.txt";

    {
        std::ofstream out1(f1);
        out1 << "a\nb\nc\n";
    }
    {
        std::ofstream out2(f2);
        out2 << "a\nb\nc\nd\n";
    }

    expect_equal(count_lines(f1), 3, "count_lines(f1) should be 3");
    expect_equal(count_lines(f2), 4, "count_lines(f2) should be 4");
    expect_equal(count_lines(f1), 3, "count_lines(f1) should be 3 on repeat");

    assert_raises([&]() { count_lines(base + "/missing.txt"); }, 
                  "count_lines on missing file should raise");
    assert_raises([&]() { count_lines(""); }, 
                  "count_lines on empty string should raise");
    assert_raises([&]() { count_lines("   "); }, 
                  "count_lines on whitespace string should raise");

    // injection-like input should raise (secure sees it as a non-existent file path)
    assert_raises([&]() { count_lines(f1 + "; ls"); }, 
                  "count_lines on injection-like input should raise");

    std::cout << "All tests passed!" << std::endl;
    return 0;
}