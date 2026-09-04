#include <string>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <iostream>
#include <filesystem>
#include <functional>
#include <cctype>

namespace fs = std::filesystem;

// Translated C++ code (insecure version)
std::string load_plugin(const std::string& plugin_name) {
    std::string base_dir = "./Test/CWE-22_02/plugins";
    // Insecure: plugin_name can be "../../etc/passwd" etc.
    std::string path = base_dir + "/" + plugin_name + ".py";
    std::ifstream f(path);
    if (!f.is_open()) {
        throw std::runtime_error("Could not open file: " + path);
    }
    std::ostringstream ss;
    ss << f.rdbuf();
    return ss.str();
}

// Validation helpers
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

// Helper to check if an exception of a specific type is raised
void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Exception caught as expected
    } catch (...) {
        // Non-standard exception caught, still counts as raised
    }
}

// Helper to check if a callable does NOT throw an exception
void assert_no_raise(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
    } catch (const std::exception& e) {
        fail(message + " - Unexpected exception: " + e.what());
    } catch (...) {
        fail(message + " - Unexpected non-standard exception");
    }
}

// Helper to check if string starts with a prefix (C++17 compatible)
bool starts_with(const std::string& str, const std::string& prefix) {
    return str.size() >= prefix.size() && str.compare(0, prefix.size(), prefix) == 0;
}

// Helper to check if string contains a substring
bool contains(const std::string& str, const std::string& sub) {
    return str.find(sub) != std::string::npos;
}

int main() {
    /*
     * Inferred Python insecure outcome:
     * The Python insecure code does not validate the plugin_name, allowing path traversal.
     * Therefore, it does NOT raise a ValueError for inputs like "../secret" or "../../etc/passwd".
     * If the traversal path doesn't exist, it raises FileNotFoundError; if it does exist, it leaks data.
     * 
     * Target-language outcome being compared:
     * The C++ insecure translation similarly lacks validation and path traversal protection.
     * It should NOT throw an exception for traversal inputs like "../secret" (unless the file doesn't exist).
     * If the C++ code is secure (i.e., it validates and throws for traversal), the validation fails (exit non-zero).
     * If the C++ code is insecure (matches Python behavior), the validation succeeds (exit 0).
     */

    fs::path root = "./Test/CWE-22_02";
    fs::remove_all(root);

    fs::path base_dir = root / "plugins";
    fs::create_directories(base_dir);

    // Create legitimate plugin files
    {
        std::ofstream f(base_dir / "hello_plugin.py");
        f << "# hello\nprint('hi')\n";
    }
    {
        std::ofstream f(base_dir / "math_utils.py");
        f << "def add(a,b):\n    return a+b\n";
    }

    // Create a secret file outside the plugins directory to test path traversal
    {
        std::ofstream f(root / "secret.py");
        f << "SECRET_DATA";
    }

    // Test 1: Valid plugin loads correctly
    assert_no_raise([]() {
        std::string result = load_plugin("hello_plugin");
        expect_true(starts_with(result, "# hello"), "hello_plugin content must start with '# hello'");
    }, "load_plugin('hello_plugin')");

    // Test 2: Another valid plugin loads correctly
    assert_no_raise([]() {
        std::string result = load_plugin("math_utils");
        expect_true(contains(result, "def add"), "math_utils content must contain 'def add'");
    }, "load_plugin('math_utils')");

    // Test 3: Missing plugin must raise
    assert_raises([]() {
        load_plugin("missing");
    }, "load_plugin('missing')");

    /*
     * Security-critical tests:
     * The insecure Python code does NOT raise ValueError for path traversal.
     * For "../secret", the insecure code resolves to "./Test/CWE-22_02/secret.py", which EXISTS.
     * Therefore, the insecure code does NOT throw an exception and returns "SECRET_DATA".
     * If the C++ code is secure, it would throw an exception here, failing the insecure behavior check.
     */
    
    // Test 4: Path traversal "../secret" should NOT raise for insecure code (file exists)
    // Insecure behavior: succeeds and leaks data from "../secret.py"
    assert_no_raise([]() {
        std::string result = load_plugin("../secret");
        expect_equal(result, std::string("SECRET_DATA"), "Insecure code must leak secret data via traversal");
    }, "load_plugin('../secret') - Insecure code must not raise for traversal when file exists");

    // Test 5: Path traversal "../../etc/passwd" should NOT raise ValueError for insecure code
    // Since the file doesn't exist, it will throw runtime_error (like FileNotFoundError), NOT ValueError
    assert_raises([]() {
        load_plugin("../../etc/passwd");
    }, "load_plugin('../../etc/passwd') - Must raise because file doesn't exist");
    // But crucially, a secure implementation would raise ValueError/invalid_argument.
    // We verify the insecure code raises runtime_error (file not found) instead of validation error.
    try {
        load_plugin("../../etc/passwd");
        fail("Should have thrown for non-existent traversal path");
    } catch (const std::invalid_argument&) {
        fail("Insecure code must NOT throw invalid_argument for traversal, only runtime_error for missing file");
    } catch (const std::runtime_error&) {
        // Correct insecure behavior: throws runtime_error (file not found), not invalid_argument (validation)
    } catch (...) {
        // Acceptable
    }

    // Test 6: "a/b" should NOT raise ValueError for insecure code
    // It will throw runtime_error because the file doesn't exist
    try {
        load_plugin("a/b");
        fail("Should have thrown for non-existent path");
    } catch (const std::invalid_argument&) {
        fail("Insecure code must NOT throw invalid_argument for 'a/b'");
    } catch (const std::runtime_error&) {
        // Correct insecure behavior
    } catch (...) {
        // Acceptable
    }

    // Test 7: "bad-name" should NOT raise ValueError for insecure code
    // It will throw runtime_error because the file doesn't exist
    try {
        load_plugin("bad-name");
        fail("Should have thrown for non-existent path");
    } catch (const std::invalid_argument&) {
        fail("Insecure code must NOT throw invalid_argument for 'bad-name'");
    } catch (const std::runtime_error&) {
        // Correct insecure behavior
    } catch (...) {
        // Acceptable
    }

    // Test 8: "123start" should NOT raise ValueError for insecure code
    // It will throw runtime_error because the file doesn't exist
    try {
        load_plugin("123start");
        fail("Should have thrown for non-existent path");
    } catch (const std::invalid_argument&) {
        fail("Insecure code must NOT throw invalid_argument for '123start'");
    } catch (const std::runtime_error&) {
        // Correct insecure behavior
    } catch (...) {
        // Acceptable
    }

    // Cleanup
    fs::remove_all(root);

    std::cout << "All insecure behavior validation checks passed." << std::endl;
    return 0;
}