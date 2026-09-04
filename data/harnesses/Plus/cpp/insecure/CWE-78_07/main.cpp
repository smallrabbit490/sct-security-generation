#include <string>
#include <vector>
#include <cstdio>
#include <stdexcept>
#include <functional>
#include <fstream>
#include <filesystem>
#include <iostream>

// --- Translated insecure C++ code (CWE-78: OS Command Injection) ---
// Inferred Python insecure outcome: The Python code uses os.popen(f"ls {directory}"),
// which is vulnerable to command injection. When given input like "dir1; ls -l",
// it executes the injected command instead of raising an error. The secure test
// expects an exception (FileNotFoundError, ValueError) for such input, but the
// insecure code does NOT raise one. The target-language outcome being compared
// is that count_directories also fails to raise an exception for injected input,
// matching the insecure behavior.

int count_directories(const std::string& directory) {
    std::string cmd = "dir /b /ad " + directory;
    FILE* pipe = _popen(cmd.c_str(), "r");
    if (!pipe) {
        throw std::runtime_error("Failed to execute command");
    }
    
    std::string result;
    char buffer[128];
    while (fgets(buffer, sizeof(buffer), pipe) != nullptr) {
        result += buffer;
    }
    int status = _pclose(pipe);
    if (status == -1) {
        throw std::runtime_error("Failed to close command stream");
    }
    
    while (!result.empty() && (result.back() == '\n' || result.back() == '\r' || result.back() == ' ' || result.back() == '\t')) {
        result.pop_back();
    }
    
    if (result.empty()) {
        return 0;
    }
    
    std::vector<std::string> file_list;
    size_t start = 0;
    size_t end = result.find('\n');
    while (end != std::string::npos) {
        file_list.push_back(result.substr(start, end - start));
        start = end + 1;
        end = result.find('\n', start);
    }
    file_list.push_back(result.substr(start));
    
    return static_cast<int>(file_list.size());
}

// --- Validation Harness Helpers ---

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_equal(int actual, int expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected " + std::to_string(expected) + ", got " + std::to_string(actual) + ")");
    }
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

// Returns true if calling fn raises an exception, false otherwise.
bool check_raises(const std::function<void()>& fn) {
    try {
        fn();
    } catch (const std::exception&) {
        return true;
    } catch (...) {
        return true;
    }
    return false;
}

// --- Main Validation Entry Point ---

int main() {
    namespace fs = std::filesystem;

    fs::path base = fs::current_path() / "Test" / "CWE-78_07";
    if (fs::exists(base)) {
        fs::remove_all(base);
    }
    fs::create_directories(base);

    fs::path dir1 = base / "dir1";
    fs::path dir2 = base / "dir2";
    fs::create_directories(dir1);
    fs::create_directories(dir2);

    for (const auto& sub : {"sub1", "sub2", "sub3"}) {
        fs::create_directories(dir1 / sub);
    }
    for (const auto& sub : {"subA", "subB"}) {
        fs::create_directories(dir2 / sub);
    }

    // Include a file that should not be counted
    {
        std::ofstream ofs((dir1 / "note.txt").string());
        ofs << "x";
    }

    // Test basic directory counting
    expect_equal(count_directories(dir1.string()), 3, "dir1 should have 3 subdirectories");
    expect_equal(count_directories(dir2.string()), 2, "dir2 should have 2 subdirectories");
    expect_equal(count_directories(dir1.string()), 3, "dir1 repeat should have 3 subdirectories");

    // Security-relevant check: Command injection vulnerability
    // The secure test expects an exception for injected input like "dir1; ls -l".
    // The insecure Python code does NOT raise an exception (it executes the injected command).
    // The insecure C++ translation also does NOT raise an exception.
    // We validate that the C++ code matches the insecure Python behavior (no exception raised).
    std::string injected_dir = dir1.string() + "; ls -l";
    bool raised_injected = check_raises([&]() { count_directories(injected_dir); });
    
    // If the vulnerability is fixed, an exception would be raised, and raised_injected would be true.
    // We want the validation to succeed (exit 0) only if the insecure behavior is present (no exception).
    if (raised_injected) {
        fail("Command injection input raised an exception; the insecure behavior is missing or fixed.");
    }

    // Check non-existent directory: insecure code may or may not raise, but we just ensure it doesn't crash unexpectedly
    std::string non_existent = (base / "non_existent").string();
    // We don't strictly enforce an exception here since the insecure code's behavior is undefined for this,
    // but we call it to ensure it runs.
    check_raises([&]() { count_directories(non_existent); });

    // Check empty string
    bool raised_empty = check_raises([&]() { count_directories(""); });
    // The insecure code might throw or not; we just verify it doesn't hard crash.
    // No strict assertion on raised_empty since insecure behavior varies.

    std::cout << "All validation checks passed. Insecure behavior confirmed." << std::endl;
    return 0;
}