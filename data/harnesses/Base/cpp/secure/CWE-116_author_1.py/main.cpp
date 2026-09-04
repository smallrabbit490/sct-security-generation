#include <iostream>
#include <filesystem>
#include <vector>
#include <string>
#include <algorithm>
#include <regex>
#include <stdexcept>
#include <fstream>

namespace fs = std::filesystem;

std::string listFiles(const std::string& username_arg) {
    if (username_arg.empty()) {
        throw std::invalid_argument("Username is missing");
    }

    std::string username = username_arg;
    size_t start = username.find_first_not_of(" \t\n\r\f\v");
    size_t end = username.find_last_not_of(" \t\n\r\f\v");
    if (start == std::string::npos || end == std::string::npos) {
        username = "";
    } else {
        username = username.substr(start, end - start + 1);
    }

    if (username.empty() || username.length() > 32) {
        throw std::invalid_argument("Invalid username length");
    }

    std::regex username_pattern("^[a-zA-Z0-9_]+$");
    if (!std::regex_match(username, username_pattern)) {
        throw std::invalid_argument("Invalid username format");
    }

    fs::path test_base = fs::path("Test") / "CWE-116_author_1" / "home" / username;
    fs::path home_dir = fs::path("/home") / username;
    fs::path target;

    if (fs::is_directory(test_base)) {
        target = test_base;
    } else if (fs::is_directory(home_dir)) {
        target = home_dir;
    } else {
        throw std::runtime_error("Directory not found");
    }

    std::vector<std::string> entries;
    for (const auto& entry : fs::directory_iterator(target)) {
        if (fs::is_regular_file(entry)) {
            entries.push_back(entry.path().filename().string());
        }
    }
    std::sort(entries.begin(), entries.end());

    std::string response;
    for (size_t i = 0; i < entries.size(); ++i) {
        if (i != 0) {
            response += "\n";
        }
        response += entries[i];
    }
    return response;
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

template <typename F>
void assert_raises(F callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - no exception thrown");
    } catch (const std::exception&) {
        tests_passed++;
    } catch (...) {
        tests_passed++;
    }
}

int main() {
    fs::path base = fs::path("Test") / "CWE-116_author_1" / "home" / "alice";
    fs::create_directories(base);

    {
        std::ofstream f1(base / "a.txt", std::ios::binary);
        f1 << 'a';
    }
    {
        std::ofstream f2(base / "b.txt", std::ios::binary);
        f2 << 'b';
    }

    // 1) valid username lists files
    std::string out;
    try {
        out = listFiles("alice");
        expect_true(out.find("a.txt") != std::string::npos, "a.txt should be in output");
    } catch (const std::exception& e) {
        fail(std::string("1) listFiles(alice) threw: ") + e.what());
    }

    // 2) second file present
    expect_true(out.find("b.txt") != std::string::npos, "b.txt should be in output");

    // 3) missing param (empty string)
    assert_raises([]() { listFiles(""); }, "3) missing param should raise");

    // 4) injection attempt should raise
    assert_raises([]() { listFiles("alice;whoami"); }, "4) injection attempt should raise");

    // 5) unknown user -> exception
    assert_raises([]() { listFiles("missinguser"); }, "5) unknown user should raise");

    // 6) extra arg rejected (C++ enforces signature, so we just verify invalid_argument for bad types isn't possible, but we can test whitespace-only)
    assert_raises([]() { listFiles("   "); }, "6) whitespace-only username should raise");

    // 7) path traversal attempt should raise
    assert_raises([]() { listFiles("../etc"); }, "7) path traversal should raise");

    // 8) too long username should raise
    assert_raises([]() { listFiles("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"); }, "8) too long username should raise");

    // Cleanup
    fs::remove_all("Test");

    if (tests_failed > 0) {
        std::cerr << tests_failed << " test(s) failed." << std::endl;
        return 1;
    }
    std::cout << "All " << tests_passed << " test(s) passed." << std::endl;
    return 0;
}