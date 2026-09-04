#include <string>
#include <filesystem>
#include <stdexcept>
#include <regex>
#include <system_error>
#include <iostream>
#include <functional>

namespace fs = std::filesystem;

// --- Mocks for external dependencies ---
static int g_raiseCalls = 0;
static int g_lowerCalls = 0;
static bool g_invalidUsernameResult = false;

bool invalidUsername(const std::string& /*username*/) {
    return g_invalidUsernameResult;
}

void raisePrivileges() {
    g_raiseCalls++;
}

void lowerPrivileges() {
    g_lowerCalls++;
}

// --- Translated Function ---
bool makeNewUserDir(const std::string& username) {
    std::string u = username;
    size_t start = u.find_first_not_of(" \t\n\r\f\v");
    if (start == std::string::npos) {
        u = "";
    } else {
        size_t end = u.find_last_not_of(" \t\n\r\f\v");
        u = u.substr(start, end - start + 1);
    }

    if (u.empty() || u.length() > 32) {
        throw std::invalid_argument("Invalid username length");
    }

    std::regex pattern(R"([A-Za-z_][A-Za-z0-9_]*)");
    if (!std::regex_match(u, pattern)) {
        throw std::invalid_argument("Invalid username characters");
    }

    if (invalidUsername(u)) {
        throw std::invalid_argument("Invalid username");
    }

    fs::path root = fs::path("Test") / "CWE-269_mitre_1" / "home";
    std::error_code ec;
    fs::create_directories(root, ec);
    if (ec) {
        throw std::runtime_error("Failed to create base directory");
    }
    fs::path path = root / u;

    raisePrivileges();
    try {
        if (fs::exists(path, ec)) {
            throw fs::filesystem_error("Directory already exists", path, std::make_error_code(std::errc::file_exists));
        }
        ec.clear();
        if (!fs::create_directory(path, ec) || ec) {
            throw std::runtime_error("Failed to create directory");
        }
    } catch (...) {
        lowerPrivileges();
        throw;
    }
    lowerPrivileges();

    return true;
}

// --- Test Harness Helpers ---
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
        std::cerr << "FAIL: " << message << " (expected " << expected << ", got " << actual << ")" << std::endl;
        std::exit(1);
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - No exception thrown");
    } catch (const std::exception&) {
        // Expected exception
    } catch (...) {
        // Also acceptable
    }
}

// --- Main Test Entry Point ---
int main() {
    fs::path base = fs::path("Test") / "CWE-269_mitre_1" / "home";
    std::error_code ec;
    fs::create_directories(base, ec);

    // Ensure clean
    fs::path alice_path = base / "alice";
    if (fs::exists(alice_path, ec)) {
        fs::remove(alice_path, ec);
    }

    // Reset mock counters
    g_raiseCalls = 0;
    g_lowerCalls = 0;
    g_invalidUsernameResult = false;

    // Test 1: Valid user creation
    bool result = makeNewUserDir("alice");
    expect_true(result, "makeNewUserDir('alice') should return true");
    expect_true(fs::exists(alice_path, ec), "Directory 'alice' should exist");
    expect_true(g_raiseCalls >= 1, "raisePrivileges should be called at least once");
    expect_true(g_lowerCalls >= 1, "lowerPrivileges should be called at least once");

    // Test 2: Duplicate directory creation throws filesystem_error
    assert_raises([]() { makeNewUserDir("alice"); }, "Creating duplicate 'alice' directory should throw");

    // Test 3: Path traversal attempt throws invalid_argument
    assert_raises([]() { makeNewUserDir("a/../b"); }, "Path traversal 'a/../b' should throw");

    // Test 4: Non-string type (simulated via invalid characters) throws invalid_argument
    assert_raises([]() { makeNewUserDir("1"); }, "Username starting with digit should throw");

    // Cleanup
    fs::remove_all("Test", ec);

    return 0;
}