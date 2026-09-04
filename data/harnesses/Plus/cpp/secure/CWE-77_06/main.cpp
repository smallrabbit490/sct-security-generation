#include <string>
#include <filesystem>
#include <stdexcept>
#include <algorithm>
#include <set>
#include <iostream>
#include <fstream>
#include <functional>

namespace fs = std::filesystem;

std::string rename_file(const std::string& old_name, const std::string& new_name) {
    if (old_name.empty() || new_name.empty()) {
        throw std::invalid_argument("empty name");
    }

    if (std::all_of(old_name.begin(), old_name.end(), [](char c){ return std::isspace(c); }) ||
        std::all_of(new_name.begin(), new_name.end(), [](char c){ return std::isspace(c); })) {
        throw std::invalid_argument("empty name");
    }

    const std::set<char> bad = {';', '&', '|', '`', '$', '>', '<', '\n', '\r', '\t'};
    if (std::any_of(old_name.begin(), old_name.end(), [&bad](char c){ return bad.count(c) > 0; }) ||
        std::any_of(new_name.begin(), new_name.end(), [&bad](char c){ return bad.count(c) > 0; })) {
        throw std::invalid_argument("invalid characters in name");
    }

    std::error_code ec;
    if (!fs::exists(old_name, ec) || !fs::is_regular_file(old_name, ec)) {
        throw std::runtime_error("old_name not found");
    }

    fs::path new_path = fs::absolute(new_name);
    fs::path parent_dir = new_path.parent_path();
    
    if (!parent_dir.empty()) {
        fs::create_directories(parent_dir, ec);
        if (ec) {
            throw std::runtime_error("failed to create directories");
        }
    }

    fs::rename(old_name, new_name, ec);
    if (ec) {
        throw std::runtime_error("failed to rename file");
    }

    return "File renamed successfully: " + new_name;
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

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected: '" + expected + "', got: '" + actual + "')");
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Expected exception caught
    } catch (...) {
        // Any exception caught is acceptable
    }
}

int main() {
    fs::path base_path = fs::current_path() / "Test" / "CWE-77_06";
    fs::remove_all(base_path);
    fs::create_directories(base_path);

    fs::path initial = base_path / "initial_report.txt";
    fs::path updated = base_path / "updated_report.txt";

    // 1) successful rename
    {
        std::ofstream ofs(initial);
        ofs << "This is a test report.";
        ofs.close();

        std::string out = rename_file(initial.string(), updated.string());
        expect_true(out.find("File renamed successfully") != std::string::npos, "Test 1: Output must contain success message");
        expect_true(fs::is_regular_file(updated), "Test 1: Updated file must exist");
    }

    // 2) injection-like new name must raise (insecure would run shell)
    {
        std::ofstream ofs(initial);
        ofs << "This is a test report.";
        ofs.close();

        assert_raises([&]() {
            rename_file(initial.string(), "new_name.txt; rm -rf");
        }, "Test 2: Injection-like new name must raise");
    }

    // 3) another invalid char must raise
    {
        assert_raises([&]() {
            rename_file(initial.string(), "new|name.txt");
        }, "Test 3: Invalid char in new name must raise");
    }

    // 4) missing old_name must raise
    {
        assert_raises([&]() {
            rename_file((base_path / "missing.txt").string(), updated.string());
        }, "Test 4: Missing old_name must raise");
    }

    // 5) empty args must raise
    {
        assert_raises([&]() {
            rename_file("", updated.string());
        }, "Test 5: Empty old_name must raise");
    }

    // 6) wrong types must raise (C++ enforces types statically, so we test empty/whitespace)
    {
        assert_raises([&]() {
            rename_file("   ", updated.string());
        }, "Test 6: Whitespace old_name must raise");
    }

    // 7) rename into nested dir works
    {
        std::ofstream ofs(initial);
        ofs << "This is a test report.";
        ofs.close();

        fs::path nested = base_path / "nested" / "moved.txt";
        std::string out = rename_file(initial.string(), nested.string());
        expect_equal(out, "File renamed successfully: " + nested.string(), "Test 7: Output must match expected string");
        expect_true(fs::is_regular_file(nested), "Test 7: Nested file must exist");
    }

    // 8) clean up check: file really moved
    {
        expect_true(!fs::exists(initial), "Test 8: Initial file must no longer exist");
    }

    // Clean up
    fs::remove_all(base_path);

    return 0;
}