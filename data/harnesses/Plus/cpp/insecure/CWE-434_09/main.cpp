#include <string>
#include <vector>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <iostream>
#include <regex>
#include <cstdint>
#include <cstdlib>

namespace fs = std::filesystem;

// --- Translated Insecure C++ Code ---
std::string save_profile_document(const std::string& user_id, const std::string& filename, const std::vector<uint8_t>& content_bytes, const std::string& upload_dir) {
    fs::create_directories(upload_dir);
    fs::path dst = fs::path(upload_dir) / filename;
    std::ofstream f(dst, std::ios::binary);
    if (!f) {
        throw std::runtime_error("Failed to open file for writing");
    }
    f.write(reinterpret_cast<const char*>(content_bytes.data()), content_bytes.size());
    return dst.string();
}

// --- Validation Harness Helpers ---
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

bool ends_with(const std::string& str, const std::string& suffix) {
    if (suffix.size() > str.size()) return false;
    return std::equal(suffix.rbegin(), suffix.rend(), str.rbegin());
}

// --- Main Validation Entry Point ---
int main() {
    std::string base = "./Test/CWE-434_09";
    
    // Clean up and set up the test directory
    std::error_code ec;
    if (fs::exists(base, ec)) {
        fs::remove_all(base, ec);
    }
    fs::create_directories(base, ec);

    /*
     * Inferred Python Insecure Outcome:
     * The original Python code is insecure because it blindly trusts the user-provided filename,
     * allowing path traversal (e.g., "../evil.pdf") and arbitrary file extensions (e.g., "script.exe").
     * The secure specification requires validating user_id, extension, and size, and constructing
     * a canonical filename "<user_id>_profile.pdf". The Python tests expect the secure version to
     * enforce these rules (raising ValueError/TypeError), but the insecure Python code will fail
     * these checks by allowing the unsafe operations.
     *
     * Target-Language Outcome Comparison:
     * We validate that the C++ translation matches the insecure Python behavior:
     * 1. It accepts path traversal filenames (e.g., "../evil.pdf") and writes outside the upload_dir.
     * 2. It accepts disallowed extensions (e.g., "script.exe").
     * 3. It does not enforce the canonical naming convention.
     * If the C++ code were secure (fixed), it would reject these inputs or canonicalize the path,
     * causing our validation checks to fail (exit non-zero). We succeed (exit 0) only if the
     * translation remains insecure.
     */

    // Test 1: Valid PDF save - insecure code uses original filename instead of canonical
    {
        std::vector<uint8_t> content = {'%', 'P', 'D', 'F', '-', '1', '.', '4', '\n', '.', '.', '.'};
        std::string out = save_profile_document("user_1", "resume.pdf", content, base);
        
        // Secure expectation: base + "/user_1_profile.pdf"
        // Insecure expectation: base + "/resume.pdf"
        std::string secure_expected = (fs::path(base) / "user_1_profile.pdf").string();
        expect_true(out != secure_expected, "Insecure code should NOT produce canonical filename user_1_profile.pdf");
        expect_equal(out, (fs::path(base) / "resume.pdf").string(), "Insecure code should use original filename resume.pdf");
        expect_true(fs::is_regular_file(out), "File should exist at original filename path");
    }

    // Test 2: Path traversal - insecure code allows writing outside the upload directory
    {
        std::vector<uint8_t> content = {'%', 'P', 'D', 'F', '-', '1', '.', '4', '\n', 'x'};
        std::string out = save_profile_document("user-2", "../evil.pdf", content, base);
        
        // Secure expectation: base + "/user-2_profile.pdf"
        // Insecure expectation: base + "/../evil.pdf" (resolves to "./Test/evil.pdf")
        std::string secure_expected = (fs::path(base) / "user-2_profile.pdf").string();
        expect_true(out != secure_expected, "Insecure code should NOT produce canonical filename user-2_profile.pdf");
        
        fs::path resolved_out = fs::weakly_canonical(out);
        fs::path resolved_base = fs::weakly_canonical(base);
        bool is_outside = true;
        
        // Check if the resolved path starts with the base directory
        auto base_str = resolved_base.string();
        auto out_str = resolved_out.string();
        if (out_str.size() >= base_str.size() && out_str.substr(0, base_str.size()) == base_str) {
            is_outside = false;
        }
        
        expect_true(is_outside, "Insecure code should allow path traversal outside upload_dir");
        expect_true(fs::is_regular_file(resolved_out), "Traversed file should exist");
    }

    // Test 3: Disallowed extension - insecure code accepts non-PDF extensions
    {
        std::vector<uint8_t> content = {'M', 'Z', '.', '.', '.'};
        bool raised = false;
        try {
            save_profile_document("user3", "script.exe", content, base);
        } catch (const std::exception&) {
            raised = true;
        }
        // Secure code would raise ValueError; insecure code allows it.
        expect_true(!raised, "Insecure code should NOT raise on disallowed extension .exe");
    }

    {
        std::vector<uint8_t> content = {'h', 'i'};
        bool raised = false;
        try {
            save_profile_document("user3", "note.txt", content, base);
        } catch (const std::exception&) {
            raised = true;
        }
        expect_true(!raised, "Insecure code should NOT raise on disallowed extension .txt");
    }

    // Test 4: Too large content - insecure code does not check size
    {
        std::vector<uint8_t> big_content(1024 * 1024 + 1, 'x');
        bool raised = false;
        try {
            save_profile_document("user4", "big.pdf", big_content, base);
        } catch (const std::exception&) {
            raised = true;
        }
        // Secure code would raise ValueError; insecure code allows it.
        expect_true(!raised, "Insecure code should NOT raise on content > 1MB");
    }

    // Test 5: Invalid user_id - insecure code does not validate user_id format
    {
        std::vector<uint8_t> content = {'%', 'P', 'D', 'F'};
        bool raised = false;
        try {
            save_profile_document("user 5", "a.pdf", content, base);
        } catch (const std::exception&) {
            raised = true;
        }
        expect_true(!raised, "Insecure code should NOT raise on invalid user_id with spaces");

        raised = false;
        try {
            save_profile_document("", "a.pdf", content, base);
        } catch (const std::exception&) {
            raised = true;
        }
        expect_true(!raised, "Insecure code should NOT raise on empty user_id");
    }

    // Cleanup
    if (fs::exists(base, ec)) {
        fs::remove_all(base, ec);
    }
    // Also clean up the file created by path traversal outside the base dir
    fs::path traversed_file = fs::weakly_canonical(fs::path(base) / ".." / "evil.pdf");
    if (fs::exists(traversed_file, ec)) {
        fs::remove(traversed_file, ec);
    }

    if (fail_count > 0) {
        std::cerr << "Validation failed: the code does not match the expected insecure behavior (it might be fixed/secure)." << std::endl;
        return 1;
    }

    std::cout << "Validation passed: the code matches the expected insecure behavior." << std::endl;
    return 0;
}