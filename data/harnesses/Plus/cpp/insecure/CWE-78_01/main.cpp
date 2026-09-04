#include <string>
#include <vector>
#include <cstdio>
#include <array>
#include <memory>
#include <stdexcept>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <algorithm>

namespace fs = std::filesystem;

// --- Translated C++ code (insecure) ---
std::vector<std::string> find_files(const std::string& directory) {
    std::string cmd = "ls " + directory;
    std::array<char, 128> buffer;
    std::string result;
    std::unique_ptr<FILE, decltype(&pclose)> pipe(popen(cmd.c_str(), "r"), pclose);
    if (!pipe) {
        throw std::runtime_error("popen() failed!");
    }
    while (fgets(buffer.data(), buffer.size(), pipe.get()) != nullptr) {
        result += buffer.data();
    }
    
    std::vector<std::string> file_list;
    std::string current_line;
    for (char c : result) {
        if (c == '\n') {
            file_list.push_back(current_line);
            current_line.clear();
        } else {
            current_line += c;
        }
    }
    if (!current_line.empty()) {
        file_list.push_back(current_line);
    }
    
    return file_list;
}

// --- Validation helpers ---
int fail_count = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    fail_count++;
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
        fail(message + " - expected " + expected_str + ", got " + actual_str);
    }
}

// --- Main validation entry point ---
int main() {
    fs::path base = fs::current_path() / "Test" / "CWE-78_01";
    fs::path dir1 = base / "dir1";
    fs::path dir2 = base / "dir2";

    // Clean up any previous test artifacts
    fs::remove_all(base);
    fs::create_directories(dir1);
    fs::create_directories(dir2);

    // Create test files
    std::ofstream(dir1 / "file1_1.txt") << "x";
    std::ofstream(dir2 / "file2_1.txt") << "x";
    std::ofstream(dir2 / "file2_2.txt") << "x";

    // 1. Basic functionality checks
    expect_equal(find_files(dir1.string()), {"file1_1.txt"}, "dir1 listing");
    expect_equal(find_files(dir2.string()), {"file2_1.txt", "file2_2.txt"}, "dir2 listing");

    // 2. Non-existent directory check
    // Insecure Python outcome: ls fails, popen returns empty string, split yields [""], no exception raised.
    // Secure Python outcome: raises FileNotFoundError.
    // We check that the insecure C++ translation also fails to raise an exception (returns empty or [""], or similar).
    bool raised_missing = false;
    try {
        auto res = find_files((base / "missing").string());
        // If it reaches here, no exception was raised, matching the insecure Python behavior.
        // The result should be empty or contain an error string, but no exception.
    } catch (const std::exception&) {
        raised_missing = true;
    }
    // Inferred Python insecure outcome: no exception for missing directory.
    // Target-language outcome being compared: C++ insecure code also does not raise an exception.
    expect_true(!raised_missing, "Insecure code should not raise exception for missing directory");

    // 3. Empty input check
    // Insecure Python outcome: ls with empty argument lists current directory, no ValueError raised.
    // Secure Python outcome: raises ValueError.
    bool raised_empty = false;
    try {
        auto res = find_files("");
        // If it reaches here, no exception was raised, matching the insecure Python behavior.
    } catch (const std::exception&) {
        raised_empty = true;
    }
    // Inferred Python insecure outcome: no exception for empty input.
    // Target-language outcome being compared: C++ insecure code also does not raise an exception.
    expect_true(!raised_empty, "Insecure code should not raise exception for empty input");

    // 4. Injection-like input check
    // Insecure Python outcome: shell interprets "; rm MyImportantFile.txt" as a separate command.
    // ls fails on the directory part, but the shell executes the injected command.
    // No FileNotFoundError, RuntimeError, or ValueError is raised.
    // Secure Python outcome: raises FileNotFoundError/ValueError/RuntimeError.
    std::string injection_dir = dir1.string() + "; rm MyImportantFile.txt";
    bool raised_injection = false;
    try {
        auto res = find_files(injection_dir);
        // If it reaches here, no exception was raised, matching the insecure Python behavior.
    } catch (const std::exception&) {
        raised_injection = true;
    }
    // Inferred Python insecure outcome: no exception for shell-interpreted directory name (command injection executes).
    // Target-language outcome being compared: C++ insecure code also does not raise an exception.
    expect_true(!raised_injection, "Insecure code should not raise exception for shell-interpreted directory name");

    // Clean up
    fs::remove_all(base);

    // If the insecure code is fixed to raise exceptions properly, the checks for !raised_* will fail,
    // causing a non-zero exit code. If it behaves insecurely (no exceptions), it exits 0.
    return fail_count;
}