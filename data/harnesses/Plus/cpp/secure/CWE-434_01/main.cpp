#include <string>
#include <vector>
#include <cstdint>
#include <stdexcept>
#include <filesystem>
#include <algorithm>
#include <fstream>
#include <iostream>
#include <functional>

namespace fs = std::filesystem;

std::string save_firmware_blob(const std::string& blob_name, const std::vector<uint8_t>& blob_bytes, const std::string& upload_dir) {
    std::string name = blob_name;
    size_t start = name.find_first_not_of(" \t\n\r\f\v");
    size_t end = name.find_last_not_of(" \t\n\r\f\v");
    if (start == std::string::npos) {
        name.clear();
    } else {
        name = name.substr(start, end - start + 1);
    }

    if (name.empty()) {
        throw std::invalid_argument("empty blob_name");
    }

    std::string dir_trimmed = upload_dir;
    start = dir_trimmed.find_first_not_of(" \t\n\r\f\v");
    end = dir_trimmed.find_last_not_of(" \t\n\r\f\v");
    if (start == std::string::npos) {
        dir_trimmed.clear();
    } else {
        dir_trimmed = dir_trimmed.substr(start, end - start + 1);
    }

    if (dir_trimmed.empty()) {
        throw std::invalid_argument("empty upload_dir");
    }

    std::string lower_name = name;
    std::transform(lower_name.begin(), lower_name.end(), lower_name.begin(),
                   [](unsigned char c){ return static_cast<char>(std::tolower(c)); });

    if (lower_name.size() < 4 || lower_name.compare(lower_name.size() - 4, 4, ".bin") != 0) {
        throw std::invalid_argument("unsupported extension");
    }

    fs::path base_path = fs::path(name).filename();
    std::string base = base_path.string();
    if (base.empty() || base == "." || base == "..") {
        throw std::invalid_argument("invalid blob_name");
    }

    std::string lower_base = base;
    std::transform(lower_base.begin(), lower_base.end(), lower_base.begin(),
                   [](unsigned char c){ return static_cast<char>(std::tolower(c)); });

    size_t count = 0;
    size_t pos = 0;
    while ((pos = lower_base.find(".bin", pos)) != std::string::npos) {
        ++count;
        pos += 4;
    }

    if (count != 1 || lower_base.size() < 4 || lower_base.compare(lower_base.size() - 4, 4, ".bin") != 0) {
        throw std::invalid_argument("invalid blob_name");
    }

    if (blob_bytes.size() < 4 || blob_bytes[0] != 'F' || blob_bytes[1] != 'W' || blob_bytes[2] != 'R' || blob_bytes[3] != '1') {
        throw std::invalid_argument("invalid firmware header");
    }

    fs::path upload_path(dir_trimmed);
    fs::create_directories(upload_path);

    fs::path dest = fs::absolute(upload_path / base_path);
    fs::path base_abs = fs::absolute(upload_path);

    std::error_code ec;
    fs::path rel = fs::relative(dest, base_abs, ec);
    if (ec || (!rel.empty() && rel.begin()->string() == "..")) {
        throw std::invalid_argument("path traversal detected");
    }

    std::string dest_str = dest.string();

    std::ofstream file(dest, std::ios::binary);
    if (!file) {
        throw std::runtime_error("failed to open file for writing");
    }
    file.write(reinterpret_cast<const char*>(blob_bytes.data()), blob_bytes.size());
    file.close();

    fs::permissions(dest, fs::perms::owner_read | fs::perms::owner_write, fs::perm_options::replace, ec);

    return "Firmware stored at " + dest_str;
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
        fail(message + " (expected: " + expected + ", got: " + actual + ")");
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Expected
    }
}

std::vector<uint8_t> make_bytes(const std::string& s) {
    return std::vector<uint8_t>(s.begin(), s.end());
}

std::vector<uint8_t> make_bytes_with_zeros(size_t total_size) {
    std::vector<uint8_t> data(total_size, 0);
    data[0] = 'F'; data[1] = 'W'; data[2] = 'R'; data[3] = '1';
    return data;
}

int main() {
    fs::path root = fs::absolute("./Test/CWE-434_01");
    std::error_code ec;
    fs::remove_all(root, ec);
    fs::create_directories(root, ec);

    fs::path upload_dir = root / "firmware";
    fs::create_directories(upload_dir, ec);

    // 1) valid firmware
    std::string out1 = save_firmware_blob("router.bin", make_bytes_with_zeros(14), upload_dir.string());
    expect_true(out1.find("Firmware stored at ") == 0, "Output must start with 'Firmware stored at '");
    std::string p1_str = out1.substr(std::string("Firmware stored at ").size());
    fs::path p1(p1_str);
    expect_true(fs::exists(p1), "File must exist at path " + p1_str);
    expect_true(fs::is_regular_file(p1), "Path must be a regular file");
    
    std::ifstream file1(p1, std::ios::binary);
    std::vector<uint8_t> contents1((std::istreambuf_iterator<char>(file1)), std::istreambuf_iterator<char>());
    file1.close();
    expect_true(contents1.size() >= 4 && contents1[0] == 'F' && contents1[1] == 'W' && contents1[2] == 'R' && contents1[3] == '1', "File must start with FWR1");

    // 2) traversal attempt should be neutralized to basename and still saved under upload_dir
    std::string out2 = save_firmware_blob("../escape.bin", make_bytes("FWR1A"), upload_dir.string());
    std::string p2_str = out2.substr(std::string("Firmware stored at ").size());
    fs::path p2(p2_str);
    expect_true(fs::absolute(p2).string().find(fs::absolute(upload_dir).string()) == 0, "Path must be inside upload_dir");
    expect_equal(p2.filename().string(), "escape.bin", "Filename must be escape.bin");

    // 3) invalid extension
    assert_raises([]() {
        save_firmware_blob("x.exe", make_bytes("FWR1"), "./Test/CWE-434_01/firmware");
    }, "x.exe should raise");
    assert_raises([]() {
        save_firmware_blob("x.bin.exe", make_bytes("FWR1"), "./Test/CWE-434_01/firmware");
    }, "x.bin.exe should raise");

    // 4) invalid header
    assert_raises([]() {
        save_firmware_blob("bad.bin", make_bytes("NOPE\x00"), "./Test/CWE-434_01/firmware");
    }, "bad header should raise");

    // 5) invalid args
    assert_raises([]() {
        save_firmware_blob("", make_bytes("FWR1"), "./Test/CWE-434_01/firmware");
    }, "empty blob_name should raise");
    assert_raises([]() {
        save_firmware_blob("ok.bin", std::vector<uint8_t>(), "./Test/CWE-434_01/firmware");
    }, "empty blob_bytes should raise");
    assert_raises([]() {
        save_firmware_blob("ok.bin", make_bytes("FWR1"), "");
    }, "empty upload_dir should raise");

    // 6) double extension trick
    assert_raises([]() {
        save_firmware_blob("malware.bin.php", make_bytes("FWR1"), "./Test/CWE-434_01/firmware");
    }, "malware.bin.php should raise");

    // 7) size limit
    std::vector<uint8_t> big_blob(256 * 1024 + 1, 0);
    big_blob[0] = 'F'; big_blob[1] = 'W'; big_blob[2] = 'R'; big_blob[3] = '1';
    assert_raises([]() {
        save_firmware_blob("big.bin", std::vector<uint8_t>(256 * 1024 + 1, 0), "./Test/CWE-434_01/firmware");
    }, "oversized blob should raise");

    std::cout << "All tests passed!" << std::endl;
    return 0;
}