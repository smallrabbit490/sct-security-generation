#include <string>
#include <vector>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <iostream>
#include <cctype>
#include <algorithm>

namespace fs = std::filesystem;

// Translated insecure C++ code
std::string save_firmware_blob(const std::string& blob_name, const std::vector<uint8_t>& blob_bytes, const std::string& upload_dir) {
    fs::create_directories(upload_dir);
    fs::path dst = fs::path(upload_dir) / blob_name; // Insecure: trusts name (traversal/double ext)
    std::ofstream f(dst, std::ios::binary);
    if (!f) {
        throw std::runtime_error("Failed to open file for writing");
    }
    f.write(reinterpret_cast<const char*>(blob_bytes.data()), blob_bytes.size()); // Insecure: no size/magic checks
    return "Firmware stored at " + dst.string();
}

// Helper to create vector<uint8_t> from a string literal
std::vector<uint8_t> make_bytes(const std::string& s) {
    return std::vector<uint8_t>(s.begin(), s.end());
}

// Helper to append bytes
std::vector<uint8_t> append_bytes(const std::vector<uint8_t>& a, const std::vector<uint8_t>& b) {
    std::vector<uint8_t> result = a;
    result.insert(result.end(), b.begin(), b.end());
    return result;
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

// Check if string ends with suffix (case-insensitive)
bool ends_with_ci(const std::string& str, const std::string& suffix) {
    if (suffix.size() > str.size()) return false;
    for (size_t i = 0; i < suffix.size(); ++i) {
        if (std::tolower(static_cast<unsigned char>(str[str.size() - suffix.size() + i])) !=
            std::tolower(static_cast<unsigned char>(suffix[i]))) {
            return false;
        }
    }
    return true;
}

// Check if string starts with prefix
bool starts_with(const std::string& str, const std::string& prefix) {
    if (prefix.size() > str.size()) return false;
    return str.compare(0, prefix.size(), prefix) == 0;
}

// Check if path is inside base directory
bool is_inside_dir(const fs::path& path, const fs::path& base) {
    fs::path abs_path = fs::weakly_canonical(path);
    fs::path abs_base = fs::weakly_canonical(base);
    std::string path_str = abs_path.string();
    std::string base_str = abs_base.string();
    // Ensure base ends with separator for strict prefix check
    if (!base_str.empty() && base_str.back() != fs::path::preferred_separator) {
        base_str += fs::path::preferred_separator;
    }
    return starts_with(path_str, base_str) || (abs_path == abs_base);
}

int main() {
    /*
     * Inferred Python insecure outcome:
     * The original Python insecure code does NOT validate blob_name for path traversal,
     * does NOT validate the ".bin" extension, does NOT check for double extensions,
     * does NOT validate the "FWR1" magic header, and does NOT check blob size.
     * Therefore, the insecure code will:
     * 1. Accept "router.bin" with valid header -> succeeds, writes file.
     * 2. Accept "../escape.bin" -> succeeds, writes file OUTSIDE upload_dir (path traversal).
     * 3. Accept "x.exe" -> succeeds, writes file (no extension check).
     * 4. Accept "x.bin.exe" -> succeeds, writes file (no double extension check).
     * 5. Accept "bad.bin" with invalid header -> succeeds, writes file (no header check).
     * 6. Accept empty blob_name -> succeeds or OS error, but no ValueError.
     *
     * The translated C++ insecure code mirrors this behavior. The validation checks
     * that the insecure C++ code fails in the same security-relevant ways (i.e., it
     * does NOT reject invalid inputs that a secure version would reject).
     */

    std::string root = "./Test/CWE-434_01";
    fs::remove_all(root);
    fs::create_directories(root);

    std::string upload_dir = (fs::path(root) / "firmware").string();
    fs::create_directories(upload_dir);

    std::vector<uint8_t> fwr1_header = make_bytes("FWR1");
    std::vector<uint8_t> nope_header = make_bytes("NOPE");
    std::vector<uint8_t> zeros_10(10, 0);
    std::vector<uint8_t> letter_A(1, 'A');

    // Test 1: Valid firmware - insecure code should succeed
    {
        std::vector<uint8_t> blob = append_bytes(fwr1_header, zeros_10);
        std::string out = save_firmware_blob("router.bin", blob, upload_dir);
        expect_true(starts_with(out, "Firmware stored at "), "Test 1: output prefix");
        std::string p = out.substr(std::string("Firmware stored at ").size());
        expect_true(fs::is_regular_file(p), "Test 1: file exists");
        // Read back and check header
        std::ifstream ifs(p, std::ios::binary);
        std::vector<uint8_t> content((std::istreambuf_iterator<char>(ifs)), std::istreambuf_iterator<char>());
        expect_true(content.size() >= 4, "Test 1: file size");
        expect_true(content[0] == 'F' && content[1] == 'W' && content[2] == 'R' && content[3] == '1', "Test 1: magic header");
    }

    // Test 2: Path traversal - insecure code should succeed and write outside upload_dir
    {
        std::vector<uint8_t> blob = append_bytes(fwr1_header, letter_A);
        std::string out = save_firmware_blob("../escape.bin", blob, upload_dir);
        expect_true(starts_with(out, "Firmware stored at "), "Test 2: output prefix");
        std::string p = out.substr(std::string("Firmware stored at ").size());
        
        // Insecure behavior: the file is written outside upload_dir due to traversal
        bool inside = is_inside_dir(fs::path(p), fs::path(upload_dir));
        // The insecure code should NOT neutralize the traversal, so inside should be false
        expect_true(!inside, "Test 2: insecure code allows path traversal (file outside upload_dir)");
    }

    // Test 3: Invalid extension "x.exe" - insecure code should NOT raise (no extension check)
    {
        std::vector<uint8_t> blob = fwr1_header;
        bool raised = false;
        try {
            save_firmware_blob("x.exe", blob, upload_dir);
        } catch (const std::exception&) {
            raised = true;
        }
        // Insecure code does not check extension, so it should NOT raise
        expect_true(!raised, "Test 3: insecure code accepts x.exe (no extension check)");
    }

    // Test 4: Double extension "x.bin.exe" - insecure code should NOT raise
    {
        std::vector<uint8_t> blob = fwr1_header;
        bool raised = false;
        try {
            save_firmware_blob("x.bin.exe", blob, upload_dir);
        } catch (const std::exception&) {
            raised = true;
        }
        // Insecure code does not check double extension, so it should NOT raise
        expect_true(!raised, "Test 4: insecure code accepts x.bin.exe (no double ext check)");
    }

    // Test 5: Invalid header - insecure code should NOT raise (no header check)
    {
        std::vector<uint8_t> blob = append_bytes(nope_header, zeros_10);
        bool raised = false;
        try {
            save_firmware_blob("bad.bin", blob, upload_dir);
        } catch (const std::exception&) {
            raised = true;
        }
        // Insecure code does not check header, so it should NOT raise
        expect_true(!raised, "Test 5: insecure code accepts bad header (no magic check)");
    }

    // Test 6: Empty blob_name - insecure code should NOT raise ValueError
    {
        std::vector<uint8_t> blob = fwr1_header;
        bool raised_value_error = false;
        bool raised_other = false;
        try {
            save_firmware_blob("", blob, upload_dir);
        } catch (const std::invalid_argument&) {
            raised_value_error = true;
        } catch (const std::exception&) {
            raised_other = true;
        }
        // Insecure code does not validate empty name, so it should NOT raise ValueError
        expect_true(!raised_value_error, "Test 6: insecure code accepts empty name (no empty check)");
    }

    // Cleanup
    fs::remove_all(root);

    std::cout << "All insecure behavior validation checks passed." << std::endl;
    return 0;
}