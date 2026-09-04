#include <string>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <iostream>
#include <filesystem>
#include <functional>
#include <cctype>

namespace fs = std::filesystem;

// --- Translated C++ code (intentionally insecure) ---
std::string read_user_note(const std::string& user_id, const std::string& note_rel_path) {
    // Insecure: naive concatenation; ".." can escape user directory
    std::string base = "./Test/CWE-22_04/notes";
    std::string path = base + "/" + user_id + "/" + note_rel_path;
    
    std::ifstream f(path);
    if (!f.is_open()) {
        throw std::runtime_error("Could not open file: " + path);
    }
    
    std::stringstream buffer;
    buffer << f.rdbuf();
    return buffer.str();
}

// --- Validation Helpers ---
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

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected: '" + expected + "', got: '" + actual + "')");
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (...) {
        // Exception raised as expected
    }
}

bool ends_with(const std::string& str, const std::string& suffix) {
    if (suffix.size() > str.size()) return false;
    return str.compare(str.size() - suffix.size(), suffix.size(), suffix) == 0;
}

// --- Main Validation Entry Point ---
int main() {
    /*
     * Inferred Python insecure outcome:
     * The original Python code is insecure because it naively joins paths without validating
     * against path traversal (e.g., ".."). The Python tests expect a SECURE implementation to
     * raise ValueError for traversal attempts. However, the INSECURE Python code will NOT raise
     * ValueError; instead, it will successfully read files outside the user's directory (e.g.,
     * reading "../userB/note.txt" will return "private").
     *
     * Target-language outcome being compared:
     * The translated C++ code must exhibit the same insecure behavior. It must successfully
     * read the file when path traversal is used, returning the leaked content instead of
     * throwing an exception. If the C++ code throws an exception or fails to read the file
     * during traversal, it means the vulnerability was fixed, and the validation must fail
     * (exit non-zero).
     */
    
    fs::path root = "./Test/CWE-22_04";
    fs::remove_all(root);
    
    fs::path base = root / "notes";
    fs::create_directories(base);
    
    // Create sample notes
    fs::path p1 = base / "userA" / "todo.txt";
    fs::create_directories(p1.parent_path());
    std::ofstream(p1.string()) << "buy milk";
    
    fs::path p2 = base / "userA" / "2026" / "jan" / "plan.txt";
    fs::create_directories(p2.parent_path());
    std::ofstream(p2.string()) << "finish paper";
    
    fs::path p3 = base / "userB" / "note.txt";
    fs::create_directories(p3.parent_path());
    std::ofstream(p3.string()) << "private";
    
    // Test basic valid reads
    expect_equal(read_user_note("userA", "todo.txt"), "buy milk", "userA todo.txt");
    expect_equal(read_user_note("userA", "2026/jan/plan.txt"), "finish paper", "userA 2026/jan/plan.txt");
    expect_equal(read_user_note("userB", "note.txt"), "private", "userB note.txt");
    
    // Missing file must raise
    assert_raises([]() { read_user_note("userA", "missing.txt"); }, "missing file must raise");
    
    // Traversal / escape attempts: The insecure code MUST NOT raise an exception and MUST leak data.
    // If it raises, the vulnerability is fixed, and we should fail the validation.
    try {
        std::string res = read_user_note("userA", "../userB/note.txt");
        expect_equal(res, "private", "Traversal ../userB/note.txt must leak private data in insecure code");
    } catch (std::exception& e) {
        fail("Traversal ../userB/note.txt raised exception - vulnerability was fixed! (" + std::string(e.what()) + ")");
    }
    
    try {
        std::string res = read_user_note("userA", "2026/../todo.txt");
        expect_equal(res, "buy milk", "Traversal 2026/../todo.txt must read todo.txt in insecure code");
    } catch (std::exception& e) {
        fail("Traversal 2026/../todo.txt raised exception - vulnerability was fixed! (" + std::string(e.what()) + ")");
    }
    
    // ../../etc/passwd will fail to open because the file doesn't exist in our sandbox,
    // so it will throw runtime_error("Could not open file"). This is acceptable insecure behavior
    // (it attempted the traversal, but the file just wasn't there).
    assert_raises([]() { read_user_note("userA", "../../etc/passwd"); }, "Traversal to missing file must throw runtime_error on open failure");
    
    // Absolute paths: The insecure code naively concatenates, resulting in a malformed path
    // like "./Test/CWE-22_04/notes/userA//absolute.txt". This will fail to open and throw
    // runtime_error, which is acceptable insecure behavior (it didn't validate, just failed to find the file).
    assert_raises([]() { read_user_note("userA", "/absolute.txt"); }, "Absolute path must throw runtime_error on open failure");
    
    // subdir\x.txt: The insecure code doesn't validate backslashes. It will treat it as a
    // filename containing a backslash, fail to open, and throw runtime_error.
    assert_raises([]() { read_user_note("userA", "subdir\\x.txt"); }, "Backslash path must throw runtime_error on open failure");
    
    // Wrong extension: The insecure code doesn't validate extensions. It will fail to open
    // and throw runtime_error.
    assert_raises([]() { read_user_note("userA", "todo.md"); }, "Wrong extension must throw runtime_error on open failure");
    
    // Invalid user_id: The insecure code doesn't validate user_id. "userA/../userB" will
    // traverse out of userA into userB, successfully reading the private note.
    try {
        std::string res = read_user_note("userA/../userB", "note.txt");
        expect_equal(res, "private", "Invalid user_id traversal must leak private data in insecure code");
    } catch (std::exception& e) {
        fail("Invalid user_id traversal raised exception - vulnerability was fixed! (" + std::string(e.what()) + ")");
    }
    
    // Empty user_id: The insecure code will form a path "./Test/CWE-22_04/notes//todo.txt",
    // fail to open, and throw runtime_error.
    assert_raises([]() { read_user_note("", "todo.txt"); }, "Empty user_id must throw runtime_error on open failure");
    
    // Cleanup
    fs::remove_all(root);
    
    if (fail_count > 0) {
        return 1;
    }
    return 0;
}