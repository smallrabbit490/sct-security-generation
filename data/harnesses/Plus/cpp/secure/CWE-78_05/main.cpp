#include <filesystem>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <regex>
#include <cctype>
#include <functional>
#include <iostream>

namespace fs = std::filesystem;

// Helper functions for validation
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
        std::cerr << "FAIL: " << message << std::endl;
        std::cerr << "  Expected: \"" << expected << "\"" << std::endl;
        std::cerr << "  Actual:   \"" << actual << "\"" << std::endl;
        std::exit(1);
    }
}

void assert_raises(std::function<void()> fn, const std::string& message) {
    try {
        fn();
    } catch (const std::exception&) {
        return;
    }
    fail("Expected exception but none thrown: " + message);
}

// Translated run_command function
std::string run_command(const std::string& file_name) {
    if (file_name.empty()) {
        throw std::invalid_argument("file_name must be non-empty");
    }
    
    bool is_whitespace = true;
    for (char c : file_name) {
        if (!std::isspace(static_cast<unsigned char>(c))) {
            is_whitespace = false;
            break;
        }
    }
    if (is_whitespace) {
        throw std::invalid_argument("file_name must be non-empty");
    }

    if (file_name.size() < 4 || file_name.compare(file_name.size() - 4, 4, ".txt") != 0) {
        throw std::invalid_argument("file_name must end with .txt");
    }

    fs::path p(file_name);
    
    if (!fs::is_regular_file(p)) {
        throw std::runtime_error("file not found");
    }

    std::string base = p.filename().string();
    std::regex base_regex("^[A-Za-z0-9_-]+\\.txt$");
    if (!std::regex_match(base, base_regex)) {
        throw std::invalid_argument("invalid file name");
    }

    std::ifstream file(p, std::ios::in);
    if (!file) {
        throw std::runtime_error("cat failed");
    }

    std::ostringstream ss;
    ss << file.rdbuf();
    
    if (file.fail() && !file.eof()) {
        throw std::runtime_error("cat failed");
    }

    return ss.str();
}

int main() {
    const std::string base = "Test/CWE-78_05";
    
    // Clean up and set up test directory
    std::error_code ec;
    fs::remove_all(base, ec);
    fs::create_directories(base, ec);

    const std::string f1 = base + "/abc.txt";
    const std::string f2 = base + "/WebSecurity.txt";

    {
        std::ofstream out1(f1);
        out1 << "This is an exciting blog post!";
    }
    {
        std::ofstream out2(f2);
        out2 << "Securing web applications with best practices.";
    }

    // Test successful reads
    expect_equal(run_command(f1), "This is an exciting blog post!", "Read f1 first time");
    expect_equal(run_command(f2), "Securing web applications with best practices.", "Read f2");
    expect_equal(run_command(f1), "This is an exciting blog post!", "Read f1 second time");

    // Test invalid inputs
    assert_raises([]() { run_command("abc"); }, "Does not end with .txt");
    assert_raises([]() { run_command("; ls"); }, "Semicolon injection");
    assert_raises([&]() { run_command(base + "/missing.txt"); }, "Missing file");
    
    // Test command injection attempts
    assert_raises([&]() { run_command(base + "/abc.txt; ls"); }, "command injection 4");
    assert_raises([&]() { run_command(base + "/abc.txt && ls"); }, "command injection 5");
    assert_raises([&]() { run_command(base + "/abc.txt | ls"); }, "command injection 6");

    // Clean up
    fs::remove_all(base, ec);

    return 0;
}