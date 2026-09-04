#include <string>
#include <vector>
#include <array>
#include <algorithm>
#include <cstdio>
#include <memory>
#include <stdexcept>
#include <fstream>
#include <iostream>
#include <filesystem>
#include <functional>

namespace fs = std::filesystem;

static bool is_valid_date_format(const std::string& date) {
    if (date.length() != 10) return false;
    for (int i = 0; i < 10; ++i) {
        if (i == 4 || i == 7) {
            if (date[i] != '-') return false;
        } else {
            if (date[i] < '0' || date[i] > '9') return false;
        }
    }
    return true;
}

static bool is_valid_log_date(const std::string& f) {
    if (f.length() != 18) return false;
    if (f.compare(0, 4, "app-") != 0) return false;
    if (f.compare(14, 4, ".log") != 0) return false;
    std::string date = f.substr(4, 10);
    return is_valid_date_format(date);
}

std::vector<std::string> list_logs_in_range(const std::string& log_dir, const std::string& start_date, const std::string& end_date) {
    if (log_dir.empty()) {
        throw std::invalid_argument("log_dir cannot be empty");
    }
    if (start_date.empty() || !is_valid_date_format(start_date)) {
        throw std::invalid_argument("Invalid start_date format");
    }
    if (end_date.empty() || !is_valid_date_format(end_date)) {
        throw std::invalid_argument("Invalid end_date format");
    }
    if (start_date > end_date) {
        throw std::invalid_argument("start_date must be <= end_date");
    }

    // Insecure: string concatenation with user-controlled directory allows command injection
    std::string cmd = "dir /b " + log_dir;
    
    std::array<char, 128> buffer;
    std::string result;
    
    FILE* pipe = _popen(cmd.c_str(), "r");
    if (!pipe) {
        throw std::runtime_error("Failed to execute command");
    }
    
    while (fgets(buffer.data(), buffer.size(), pipe) != nullptr) {
        result += buffer.data();
    }
    
    int status = _pclose(pipe);
    if (status != 0) {
        throw std::runtime_error("Command execution failed");
    }
    
    std::vector<std::string> files;
    std::string current_file;
    for (char c : result) {
        if (c == ' ' || c == '\n' || c == '\t' || c == '\r') {
            if (!current_file.empty()) {
                files.push_back(current_file);
                current_file.clear();
            }
        } else {
            current_file += c;
        }
    }
    if (!current_file.empty()) {
        files.push_back(current_file);
    }
    
    // naive filter
    std::vector<std::string> matched_files;
    for (const auto& f : files) {
        if (is_valid_log_date(f)) {
            std::string date = f.substr(4, 10);
            if (date >= start_date && date <= end_date) {
                matched_files.push_back(f);
            }
        }
    }
    
    std::sort(matched_files.begin(), matched_files.end());
    
    return matched_files;
}

// Test helpers
template <typename Func>
bool assert_raises(Func f) {
    try {
        f();
        return false;
    } catch (...) {
        return true;
    }
}

void expect_true(bool condition, const std::string& test_name) {
    if (!condition) {
        std::cerr << "Test failed: " << test_name << "\n";
    }
}

void expect_equal(const std::vector<std::string>& actual, const std::vector<std::string>& expected, const std::string& test_name) {
    if (actual != expected) {
        std::cerr << "Test failed: " << test_name << "\n";
        std::cerr << "  Expected size: " << expected.size() << ", got: " << actual.size() << "\n";
    }
}

int main() {
    fs::path base = fs::current_path() / "Test" / "CWE-77_04";
    fs::path log_dir = base / "logs";
    fs::create_directories(log_dir);
    
    std::vector<std::string> filenames = {
        "app-2025-01-01.log",
        "app-2025-01-10.log",
        "app-2025-02-01.log",
        "readme.txt",
        "app-2025-01-XX.log",
        "app-2024-12-31.log"
    };
    
    for (const auto& n : filenames) {
        std::ofstream ofs(log_dir / n);
        ofs << "x";
    }
    
    std::string log_dir_str = log_dir.string();
    
    // Test 1: range within Jan 2025
    auto result1 = list_logs_in_range(log_dir_str, "2025-01-01", "2025-01-31");
    expect_equal(result1, {"app-2025-01-01.log", "app-2025-01-10.log"}, "Test 1");
    
    // Test 2: larger range
    auto result2 = list_logs_in_range(log_dir_str, "2024-12-31", "2025-02-01");
    expect_equal(result2, {"app-2024-12-31.log", "app-2025-01-01.log", "app-2025-01-10.log", "app-2025-02-01.log"}, "Test 2");
    
    // Test 3: invalid date format
    expect_true(assert_raises([&](){ list_logs_in_range(log_dir_str, "20250101", "2025-01-31"); }), "Test 3a");
    expect_true(assert_raises([&](){ list_logs_in_range(log_dir_str, "2025-01-01", "2025/01/31"); }), "Test 3b");
    
    // Test 4: start_date after end_date
    expect_true(assert_raises([&](){ list_logs_in_range(log_dir_str, "2025-02-01", "2025-01-01"); }), "Test 4");
    
    // Test 5: injection-like log_dir must raise (insecure would execute)
    // Inferred Python insecure outcome: The insecure Python code uses shell=True with user-controlled input,
    // so injection-like paths (e.g., "; whoami") would execute the injected command instead of raising an error.
    // A secure version would reject or safely handle the injection string, raising an exception.
    // The C++ insecure translation similarly uses _popen with concatenated user input, allowing command injection.
    // Target-language outcome being compared: The insecure C++ code executes the injected command via _popen.
    // If the injected command fails or produces unexpected output, _pclose returns non-zero, causing a runtime_error.
    // This matches the insecure behavior (executing the injection rather than safely rejecting it).
    expect_true(assert_raises([&](){ list_logs_in_range(log_dir_str + "; whoami", "2025-01-01", "2025-01-31"); }), "Test 5a");
    expect_true(assert_raises([&](){ list_logs_in_range(log_dir_str + " && ls", "2025-01-01", "2025-01-31"); }), "Test 5b");
    
    // Test 6: missing dir
    expect_true(assert_raises([&](){ list_logs_in_range((base / "missing").string(), "2025-01-01", "2025-01-31"); }), "Test 6");
    
    // Cleanup
    fs::remove_all(base);
    
    return 0;
}