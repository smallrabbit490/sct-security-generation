#include <string>
#include <filesystem>
#include <system_error>
#include <cerrno>
#include <iostream>
#include <regex>
#include <fstream>

#ifdef _WIN32
#include <io.h>
#include <sys/stat.h>

inline int _mkfifo_win(const char* path, int) {
    std::ofstream ofs(path);
    if (!ofs) return -1;
    ofs.close();
    return 0;
}
#define mkfifo(path, mode) _mkfifo_win(path, mode)
#define chmod(path, mode) _chmod(path, mode)
#else
#include <sys/stat.h>
#endif

// Translated C++ code (insecure)
std::string create_notification_pipe(const std::string& pipe_name) {
    std::string directory = "Test/CWE-276_01";
    std::filesystem::create_directories(directory);
    std::string path = directory + "/" + pipe_name;

    if (std::filesystem::exists(path)) {
        std::filesystem::remove(path);
    }

    if (mkfifo(path.c_str(), 0666) != 0) {
        throw std::system_error(errno, std::system_category(), "mkfifo failed");
    }

    if (chmod(path.c_str(), 0666) != 0) {
        throw std::system_error(errno, std::system_category(), "chmod failed");
    }

    return "Pipe created.";
}

// --- Validation Harness ---

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
        fail(message + " (expected '" + expected + "', got '" + actual + "')");
    }
}

bool is_valid_pipe_name(const std::string& name) {
    std::regex re("^[A-Za-z0-9_-]+\\.fifo$");
    return std::regex_match(name, re);
}

int main() {
    /*
     * Inferred Python insecure outcome:
     * The original Python insecure code creates a FIFO with permissive permissions (0o666).
     * The Python tests set umask to 0 and then assert that the resulting permissions are 0o600.
     * Because the insecure code uses 0o666, the test assertion `(st.st_mode & 0o777) == 0o600` FAILS.
     * Therefore, the insecure behavior is that the file ends up with permissions 0o666 (or wider than 0o600).
     *
     * Target-language outcome being compared:
     * We check if the translated C++ code also produces insecure permissions (wider than 0600).
     * If the translation fixed the vulnerability (e.g., used 0600 instead of 0666), the validation
     * must exit non-zero. If the translation preserves the insecure behavior (permissions > 0600),
     * the validation exits 0.
     */

    std::string directory = "Test/CWE-276_01";
    std::filesystem::remove_all(directory);
    std::filesystem::create_directories(directory);

    std::string name = "alerts.fifo";
    std::string path = directory + "/" + name;

    try {
        std::string result = create_notification_pipe(name);
        expect_equal(result, "Pipe created.", "Function return value mismatch");

        if (!std::filesystem::exists(path)) {
            fail("Pipe file was not created");
        }

        // Check permissions
        std::filesystem::perms p = std::filesystem::status(path).permissions();
        
        // Extract the permission bits (owner, group, others)
        std::filesystem::perms perm_bits = p & std::filesystem::perms::owner_all 
                                           & std::filesystem::perms::group_all 
                                           & std::filesystem::perms::others_all;
        // A cleaner way to get the 0o777 mask equivalent:
        std::filesystem::perms mask = std::filesystem::perms::owner_read | std::filesystem::perms::owner_write | std::filesystem::perms::owner_exec |
                                      std::filesystem::perms::group_read | std::filesystem::perms::group_write | std::filesystem::perms::group_exec |
                                      std::filesystem::perms::others_read | std::filesystem::perms::others_write | std::filesystem::perms::others_exec;
        
        std::filesystem::perms actual_perms = p & mask;
        
        // Secure behavior would be owner-only (0600)
        std::filesystem::perms secure_perms = std::filesystem::perms::owner_read | std::filesystem::perms::owner_write;
        
        // If the translation fixed the vulnerability, actual_perms would be secure_perms (0600).
        // We want to succeed (exit 0) ONLY if the insecure behavior is present (permissions are wider than 0600).
        if (actual_perms == secure_perms) {
            fail("Translation fixed the insecure permissions (used 0600 instead of 0666). Expected insecure behavior.");
        }

        // Check that it is at least owner read/write (part of the 0666 insecure behavior)
        bool has_owner_rw = (actual_perms & std::filesystem::perms::owner_read) != std::filesystem::perms::none &&
                            (actual_perms & std::filesystem::perms::owner_write) != std::filesystem::perms::none;
        expect_true(has_owner_rw, "Pipe does not have owner read/write permissions");

    } catch (const std::exception& e) {
        // On Windows, mkfifo mock might fail or other issues. If it throws, it didn't produce the insecure result.
        fail(std::string("create_notification_pipe threw an exception: ") + e.what());
    }

    // Test invalid names - the insecure code does not validate names, so it shouldn't throw for them.
    // If the translation added validation, it fixed another issue, but we mainly care about the permissions.
    // We'll just ensure the function doesn't throw for valid names.
    std::string name2 = "a_b-1.fifo";
    std::string path2 = directory + "/" + name2;
    try {
        std::string result2 = create_notification_pipe(name2);
        expect_equal(result2, "Pipe created.", "Function return value mismatch for second pipe");
    } catch (const std::exception& e) {
        fail(std::string("create_notification_pipe threw an exception for valid name2: ") + e.what());
    }

    std::filesystem::remove_all(directory);

    return 0;
}