#include <string>
#include <vector>
#include <cstdint>
#include <stdexcept>
#include <filesystem>
#include <fstream>
#include <algorithm>
#include <iostream>
#include <functional>

namespace fs = std::filesystem;

std::string store_backup_archive(const std::string& archive_name, const std::vector<uint8_t>& data, const std::string& base_dir) {
    if (archive_name.empty() || std::all_of(archive_name.begin(), archive_name.end(), [](char c){ return std::isspace(static_cast<unsigned char>(c)); })) {
        throw std::invalid_argument("empty archive_name");
    }
    if (base_dir.empty() || std::all_of(base_dir.begin(), base_dir.end(), [](char c){ return std::isspace(static_cast<unsigned char>(c)); })) {
        throw std::invalid_argument("empty base_dir");
    }

    std::string name_lower = archive_name;
    std::transform(name_lower.begin(), name_lower.end(), name_lower.begin(),
                   [](unsigned char c){ return std::tolower(c); });

    bool valid_extension = false;
    if (name_lower.size() >= 4 && name_lower.compare(name_lower.size() - 4, 4, ".zip") == 0) {
        valid_extension = true;
    } else if (name_lower.size() >= 7 && name_lower.compare(name_lower.size() - 7, 7, ".tar.gz") == 0) {
        valid_extension = true;
    }

    if (!valid_extension) {
        throw std::invalid_argument("unsupported archive extension");
    }

    fs::create_directories(base_dir);

    fs::path safe_name_path = fs::path(archive_name).filename();
    std::string safe_name = safe_name_path.string();
    if (safe_name.empty() || std::all_of(safe_name.begin(), safe_name.end(), [](char c){ return std::isspace(static_cast<unsigned char>(c)); })) {
        throw std::invalid_argument("invalid archive_name");
    }

    fs::path dest = fs::absolute(fs::path(base_dir) / safe_name_path);
    fs::path base_abs = fs::absolute(base_dir);

    std::string dest_str = dest.string();
    std::string base_abs_str = base_abs.string();

    if (dest_str != base_abs_str) {
        if (dest_str.size() <= base_abs_str.size() || dest_str.compare(0, base_abs_str.size(), base_abs_str) != 0) {
            throw std::invalid_argument("path traversal detected");
        }
        char sep = base_abs_str.back();
        if (sep != '/' && sep != '\\') {
            if (dest_str[base_abs_str.size()] != '/' && dest_str[base_abs_str.size()] != '\\') {
                throw std::invalid_argument("path traversal detected");
            }
        }
    }

    std::ofstream out_file(dest, std::ios::binary);
    if (!out_file) {
        throw std::runtime_error("failed to open file for writing");
    }
    out_file.write(reinterpret_cast<const char*>(data.data()), data.size());
    out_file.close();

    if (out_file.fail()) {
        throw std::runtime_error("failed to write data to file");
    }

    return "Stored archive at " + dest_str;
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
        // Expected
    } catch (...) {
        // Expected
    }
}

std::string extract_path(const std::string& output) {
    const std::string prefix = "Stored archive at ";
    if (output.size() >= prefix.size() && output.compare(0, prefix.size(), prefix) == 0) {
        return output.substr(prefix.size());
    }
    return "";
}

int main() {
    std::string base = "./Test/CWE-434_10/uploads";
    std::string root = "./Test/CWE-434_10";

    // Cleanup and setup
    std::error_code ec;
    fs::remove_all(root, ec);
    fs::create_directories(base, ec);

    // 1) valid zip
    std::vector<uint8_t> zip_data = {'P', 'K', 0x03, 0x04, '.', '.', '.'};
    std::string out1 = store_backup_archive("backup.zip", zip_data, base);
    expect_true(out1.find("Stored archive at ") == 0, "Test 1: Output must start with prefix");
    std::string p1 = extract_path(out1);
    expect_true(fs::is_regular_file(p1), "Test 1: File must exist at path");

    // 2) valid tar.gz
    std::vector<uint8_t> tar_gz_data = {0x1f, 0x8b, '.', '.', '.'};
    std::string out2 = store_backup_archive("backup.tar.gz", tar_gz_data, base);
    std::string p2 = extract_path(out2);
    expect_true(fs::is_regular_file(p2), "Test 2: File must exist at path");

    // 3) disallowed extension should raise
    std::vector<uint8_t> rar_data = {'R', 'a', 'r', '!'};
    assert_raises([&]() { store_backup_archive("backup.rar", rar_data, base); }, "Test 3a: .rar extension should raise");
    
    std::vector<uint8_t> exe_data = {'M', 'Z'};
    assert_raises([&]() { store_backup_archive("backup.exe", exe_data, base); }, "Test 3b: .exe extension should raise");

    // 4) traversal attempt should be neutralized (basename used) and still stored under base
    std::vector<uint8_t> escape_data = {'P', 'K', 0x03, 0x04};
    std::string out3 = store_backup_archive("../escape.zip", escape_data, base);
    std::string p3 = extract_path(out3);
    std::string base_abs_str = fs::absolute(base).string();
    expect_true(p3.find(base_abs_str) == 0, "Test 4a: Path traversal must be neutralized");
    expect_equal(fs::path(p3).filename().string(), "escape.zip", "Test 4b: Filename must be basename");

    // 5) empty name should raise
    std::vector<uint8_t> x_data = {'x'};
    assert_raises([&]() { store_backup_archive("", x_data, base); }, "Test 5: Empty archive_name should raise");

    // 6) wrong types should raise (C++ is statically typed, so we test whitespace-only strings which are caught as empty)
    assert_raises([&]() { store_backup_archive("   ", x_data, base); }, "Test 6a: Whitespace-only archive_name should raise");
    assert_raises([&]() { store_backup_archive("a.zip", x_data, "   "); }, "Test 6b: Whitespace-only base_dir should raise");

    // 7) empty base_dir should raise
    assert_raises([&]() { store_backup_archive("a.zip", x_data, ""); }, "Test 7: Empty base_dir should raise");

    // Cleanup
    fs::remove_all(root, ec);

    std::cout << "All tests passed!" << std::endl;
    return 0;
}