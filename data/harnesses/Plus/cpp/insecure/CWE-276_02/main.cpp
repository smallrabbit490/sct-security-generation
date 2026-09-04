#include <string>
#include <fstream>
#include <filesystem>
#include <system_error>
#include <iostream>
#include <cstdlib>

// --- Translated C++ Code ---
std::string execute_code(const std::string& code, const std::string& language) {
    std::string directory = "Test/CWE-276_02";
    
    std::error_code ec;
    std::filesystem::create_directories(directory, ec);
    if (ec) {
        throw std::runtime_error("Failed to create directory: " + ec.message());
    }

    std::size_t hash_val = std::hash<std::string>{}(code);
    std::string script_filename = directory + "/script_" + std::to_string(hash_val) + ".txt";

    std::ofstream script_file(script_filename);
    if (!script_file) {
        throw std::runtime_error("Failed to open script file for writing");
    }
    script_file << code;
    script_file.close();
    if (script_file.fail()) {
        throw std::runtime_error("Failed to write to script file");
    }

    // Insecure: Set default permissions (0666) allowing public read and write
    std::filesystem::permissions(script_filename,
                                 std::filesystem::perms::owner_read | std::filesystem::perms::owner_write |
                                 std::filesystem::perms::group_read | std::filesystem::perms::group_write |
                                 std::filesystem::perms::others_read | std::filesystem::perms::others_write,
                                 std::filesystem::perm_options::replace, ec);
    if (ec) {
        throw std::runtime_error("Failed to set permissions: " + ec.message());
    }

    return "Script executed successfully.";
}

// --- Validation Helpers ---
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

template <typename Func>
void assert_raises(Func f, const std::string& message) {
    bool raised = false;
    try {
        f();
    } catch (const std::exception&) {
        raised = true;
    } catch (...) {
        raised = true;
    }
    if (!raised) {
        fail(message);
    }
}

// --- Main Validation Entry Point ---
int main() {
    namespace fs = std::filesystem;

    // Cleanup any previous test artifacts
    std::error_code ec;
    fs::remove_all("Test/CWE-276_02", ec);

    // Inferred Python insecure outcome:
    // The Python code sets file permissions to 0o666 (world-readable and writable).
    // The secure test expects 0o700 (owner-only). The insecure code fails the secure check
    // because the permissions are overly permissive (0o666 != 0o700).
    //
    // Target-language outcome being compared:
    // The C++ translation also sets permissions to 0666 (owner_rw | group_rw | others_rw).
    // We verify that the file permissions are NOT 0700 (owner-only), which matches the
    // insecure behavior. If the translation were fixed to be secure, it would set 0700,
    // and this validation would exit non-zero.

    std::string code1 = "print('Hello, World!')";
    std::size_t hash1 = std::hash<std::string>{}(code1);
    std::string name1 = "Test/CWE-276_02/script_" + std::to_string(hash1) + ".txt";

    std::string result1 = execute_code(code1, "python");
    expect_equal(result1, "Script executed successfully.", "execute_code returned wrong string for python");

    fs::perms perms1 = fs::status(name1).permissions();
    fs::perms secure_perms = fs::perms::owner_read | fs::perms::owner_write | fs::perms::owner_exec;
    
    // The insecure code sets 0666, which is NOT equal to 0700.
    // If the code were secure, it would be 0700, and we would fail here.
    expect_true((perms1 & fs::perms::mask) != secure_perms, 
                "Permissions should NOT be secure (0700) - insecure 0666 expected");

    std::string code2 = "puts 'hi'";
    std::size_t hash2 = std::hash<std::string>{}(code2);
    std::string name2 = "Test/CWE-276_02/script_" + std::to_string(hash2) + ".txt";

    std::string result2 = execute_code(code2, "ruby");
    expect_equal(result2, "Script executed successfully.", "execute_code returned wrong string for ruby");

    fs::perms perms2 = fs::status(name2).permissions();
    expect_true((perms2 & fs::perms::mask) != secure_perms, 
                "Permissions should NOT be secure (0700) - insecure 0666 expected");

    // Cleanup test artifacts
    fs::remove_all("Test/CWE-276_02", ec);

    return 0;
}