#include <iostream>
#include <string>
#include <vector>
#include <sstream>
#include <fstream>
#include <filesystem>
#include <functional>
#include <cstdlib>

namespace fs = std::filesystem;

// ---------- Translated insecure code (refactored for testability) ----------

std::string download(const std::string& file) {
    // Parse the name to get the file path by replacing '_' with '/'
    std::string filepath;
    for (size_t i = 0; i < file.size(); ++i) {
        if (file[i] == '_') {
            filepath += '/';
        } else {
            filepath += file[i];
        }
    }

    // Send the file to the client as an attachment
    std::ifstream file_stream(filepath, std::ios::binary);
    if (file_stream.is_open()) {
        std::cout << "Content-Disposition: attachment; filename=\"" << fs::path(filepath).filename().string() << "\"\n";
        std::cout << "Content-Type: application/octet-stream\n\n";
        std::cout << file_stream.rdbuf();
        file_stream.close();
        return filepath;
    } else {
        std::cerr << "File not found: " << filepath << std::endl;
        throw std::runtime_error("File not found: " + filepath);
    }
}

// ---------- Validation helpers ----------

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
        fail(message + " (expected: '" + expected + "', got: '" + actual + "')");
    }
}

bool has_prefix(const std::string& str, const std::string& prefix) {
    if (prefix.size() > str.size()) return false;
    return str.compare(0, prefix.size(), prefix) == 0;
}

bool assert_raises(const std::function<void()>& callable) {
    try {
        callable();
        return false; // No exception thrown
    } catch (...) {
        return true; // Exception thrown
    }
}

// ---------- Main validation entry point ----------

int main() {
    // Set up the test directory structure
    fs::path base = fs::absolute(fs::path("Test") / "CWE-641_sonar_1");
    fs::path files_dir = base / "files" / "docs";

    fs::create_directories(files_dir);
    {
        std::ofstream ofs(files_dir / "readme.txt");
        ofs << "ok";
    }

    fs::path original_cwd = fs::current_path();
    fs::current_path(base);

    try {
        // Test 1: Valid file 'docs_readme.txt' should resolve to 'files/docs/readme.txt'
        // Insecure code happily processes this and returns the path
        std::string result1 = download("files_docs_readme.txt");
        std::string expected1 = "files/docs/readme.txt";
        expect_equal(result1, expected1, "Valid file path should resolve correctly");

        // Test 2: Traversal-like segments '.._.._etc_passwd' should be rejected
        // Insecure code will happily turn it into '../../etc/passwd' and attempt to send it.
        // The Python test expects ValueError, but insecure code does NOT raise it.
        // For our validation, we check that the insecure code FAILS to raise an exception
        // (which matches the insecure behavior).
        bool traversal_raises = assert_raises([]() {
            download(".._.._etc_passwd");
        });
        // Insecure code does NOT raise an exception for traversal paths (it just fails to open the file
        // and throws a generic runtime_error, but the Python test expects it to throw ValueError).
        // The key insecure behavior is that it doesn't validate/reject the traversal.
        // Since the file doesn't exist, it will throw runtime_error. assert_raises catches it.
        // But the Python test specifically expects ValueError for traversal rejection.
        // The insecure code doesn't reject traversal - it attempts it.
        // So we verify: the insecure code does NOT throw ValueError (it throws runtime_error for file not found).
        bool throws_value_error = false;
        try {
            download(".._.._etc_passwd");
        } catch (const std::runtime_error&) {
            // Insecure code throws generic runtime_error, not ValueError
        } catch (const std::invalid_argument&) {
            throws_value_error = true;
        } catch (...) {
            // Some other exception
        }
        // Insecure code should NOT throw a ValueError/invalid_argument for traversal
        expect_true(!throws_value_error, "Insecure code should not reject traversal paths with ValueError");

        // Test 3: Missing file 'docs_missing.txt' should raise FileNotFoundError
        // Insecure code throws runtime_error instead of a specific FileNotFoundError
        bool missing_raises_runtime = assert_raises([]() {
            download("docs_missing.txt");
        });
        expect_true(missing_raises_runtime, "Missing file should raise an exception");

        // Test 4: Empty file parameter should be rejected
        // Insecure code doesn't validate empty input and will attempt to open ""
        bool empty_raises = assert_raises([]() {
            download("");
        });
        // Insecure code will fail to open "" and throw runtime_error
        // Python test expects ValueError, but insecure code doesn't validate
        expect_true(empty_raises, "Empty file parameter should raise an exception");

    } catch (...) {
        fail("Unexpected exception during tests");
    }

    fs::current_path(original_cwd);

    // Cleanup
    fs::remove_all(base);

    std::cout << "Tests passed: " << tests_passed << ", failed: " << tests_failed << std::endl;

    if (tests_failed > 0) {
        return 1;
    }
    return 0;
}