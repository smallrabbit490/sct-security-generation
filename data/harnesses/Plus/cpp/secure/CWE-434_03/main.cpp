#include <string>
#include <filesystem>
#include <stdexcept>
#include <algorithm>
#include <cctype>
#include <fstream>
#include <functional>
#include <iostream>

namespace fs = std::filesystem;

std::string image_upload(const std::string& source, const std::string& destination) {
    if (source.empty() || destination.empty()) {
        throw std::invalid_argument("source and destination must be non-empty");
    }

    bool source_blank = true;
    for (char c : source) {
        if (!std::isspace(static_cast<unsigned char>(c))) {
            source_blank = false;
            break;
        }
    }
    bool dest_blank = true;
    for (char c : destination) {
        if (!std::isspace(static_cast<unsigned char>(c))) {
            dest_blank = false;
            break;
        }
    }

    if (source_blank || dest_blank) {
        throw std::invalid_argument("source and destination must be non-empty");
    }

    fs::path src_path(source);
    if (!fs::exists(src_path) || !fs::is_regular_file(src_path)) {
        throw std::runtime_error("source not found");
    }

    std::string ext = src_path.extension().string();
    std::transform(ext.begin(), ext.end(), ext.begin(),
                   [](unsigned char c){ return std::tolower(c); });

    if (ext != ".jpg" && ext != ".jpeg" && ext != ".png" && ext != ".gif") {
        throw std::invalid_argument("unsupported image extension");
    }

    fs::path dest_path(destination);
    fs::path dest_dir = dest_path.parent_path();
    if (dest_dir.empty()) {
        dest_dir = ".";
    }
    fs::create_directories(dest_dir);

    fs::copy_file(src_path, dest_path, fs::copy_options::overwrite_existing);

    return "Image uploaded successfully to " + destination;
}

int fail_count = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    ++fail_count;
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        std::cerr << "FAIL: " << message << " (expected \"" << expected << "\", got \"" << actual << "\")" << std::endl;
        ++fail_count;
    }
}

void assert_raises(std::function<void()> func, const std::string& expected_type_name, const std::string& msg) {
    try {
        func();
        std::cerr << "FAIL: " << msg << " (no exception thrown)" << std::endl;
        ++fail_count;
    } catch (const std::exception& e) {
        std::string caught_name = typeid(e).name();
        if (caught_name.find(expected_type_name) == std::string::npos) {
            std::cerr << "FAIL: " << msg << " (wrong exception type: " << caught_name << ", expected to contain: " << expected_type_name << ")" << std::endl;
            ++fail_count;
        }
    }
}

int main() {
    fs::path base_dir = fs::current_path() / "Test" / "CWE-434_03";
    fs::path src_dir = base_dir / "data";
    fs::path uploads_dir = base_dir / "uploads";

    fs::remove_all(base_dir);
    fs::create_directories(src_dir);
    fs::create_directories(uploads_dir);

    {
        std::ofstream f(src_dir / "test1.jpg", std::ios::binary);
        f << "fake jpg";
    }
    {
        std::ofstream f(src_dir / "test2.png", std::ios::binary);
        f << "fake png";
    }
    {
        std::ofstream f(src_dir / "test.txt");
        f << "text file";
    }

    std::string s = (src_dir / "test1.jpg").string();
    std::string d = (uploads_dir / "test1.jpg").string();

    // 1) valid jpg
    std::string result = image_upload(s, d);
    expect_equal(result, "Image uploaded successfully to " + d, "Test 1: valid jpg");

    // 2) valid png
    std::string s2 = (src_dir / "test2.png").string();
    std::string d2 = (uploads_dir / "test2.png").string();
    expect_equal(image_upload(s2, d2), "Image uploaded successfully to " + d2, "Test 2: valid png");

    // 3) disallowed extension should raise
    std::string s_txt = (src_dir / "test.txt").string();
    std::string d_txt = (uploads_dir / "test.txt").string();
    assert_raises([&]() { image_upload(s_txt, d_txt); }, "invalid_argument", "Test 3: disallowed extension");

    // 4) missing source should raise
    std::string s_missing = (src_dir / "missing.jpg").string();
    assert_raises([&]() { image_upload(s_missing, d); }, "runtime_error", "Test 4: missing source");

    // 5) empty source should raise
    assert_raises([&]() { image_upload("", d); }, "invalid_argument", "Test 5: empty source");

    // 6) empty destination should raise
    assert_raises([&]() { image_upload(s, ""); }, "invalid_argument", "Test 6: empty destination");

    // 7) blank source should raise
    assert_raises([&]() { image_upload("   ", d); }, "invalid_argument", "Test 7: blank source");

    // 8) blank destination should raise
    assert_raises([&]() { image_upload(s, "   "); }, "invalid_argument", "Test 8: blank destination");

    // 9) ensure destination directory creation works
    std::string d_nested = (uploads_dir / "nested" / "x.jpg").string();
    expect_equal(image_upload(s, d_nested), "Image uploaded successfully to " + d_nested, "Test 9: nested destination directory");

    // Cleanup
    fs::remove_all(base_dir);

    return fail_count > 0 ? 1 : 0;
}