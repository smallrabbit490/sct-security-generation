#include <string>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <algorithm>
#include <cctype>
#include <iostream>
#include <functional>

namespace fs = std::filesystem;

std::string upload_avatar_image(const std::string& user_id, const std::string& file_path) {
    if (user_id.empty()) {
        throw std::invalid_argument("empty user_id");
    }
    
    std::string trimmed_file_path = file_path;
    trimmed_file_path.erase(trimmed_file_path.begin(), std::find_if(trimmed_file_path.begin(), trimmed_file_path.end(), [](unsigned char ch) {
        return !std::isspace(ch);
    }));
    trimmed_file_path.erase(std::find_if(trimmed_file_path.rbegin(), trimmed_file_path.rend(), [](unsigned char ch) {
        return !std::isspace(ch);
    }).base(), trimmed_file_path.end());
    
    if (trimmed_file_path.empty()) {
        throw std::invalid_argument("empty file_path");
    }

    fs::path src_path(file_path);
    if (!fs::exists(src_path) || !fs::is_regular_file(src_path)) {
        throw std::runtime_error("file_path not found");
    }

    std::string ext = src_path.extension().string();
    std::string ext_lower = ext;
    std::transform(ext_lower.begin(), ext_lower.end(), ext_lower.begin(),
                   [](unsigned char c){ return std::tolower(c); });

    if (ext_lower != ".jpg" && ext_lower != ".png") {
        throw std::invalid_argument("unsupported extension");
    }

    fs::path base_dir = "./Test/CWE-434_06/avatar_images/";
    fs::create_directories(base_dir);

    std::string safe_user;
    for (char ch : user_id) {
        if (std::isalnum(static_cast<unsigned char>(ch)) || ch == '_' || ch == '-') {
            safe_user += ch;
        }
    }

    if (safe_user.empty()) {
        throw std::invalid_argument("invalid user_id");
    }

    fs::path dest_path = base_dir / (safe_user + "_avatar" + ext_lower);
    fs::copy_file(src_path, dest_path, fs::copy_options::overwrite_existing);

    return "Avatar image uploaded successfully.";
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
        std::cerr << "FAIL: " << message << " (expected: \"" << expected << "\", got: \"" << actual << "\")" << std::endl;
        std::exit(1);
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Expected exception caught
    }
}

bool ends_with(const std::string& str, const std::string& suffix) {
    if (suffix.size() > str.size()) return false;
    return std::equal(suffix.rbegin(), suffix.rend(), str.rbegin());
}

int main() {
    fs::path base_dir = "./Test/CWE-434_06/";
    fs::path example_files_dir = base_dir / "example_files";
    fs::path avatar_images_dir = base_dir / "avatar_images";

    // Clean up and set up directories
    fs::remove_all(base_dir);
    fs::create_directories(example_files_dir);
    fs::create_directories(avatar_images_dir);

    // Create safe jpg
    fs::path safe_jpg = example_files_dir / "user123_avatar.jpg";
    {
        std::ofstream ofs(safe_jpg, std::ios::binary);
        ofs.write("\xff\xd8\xff", 3);
    }

    // Create safe png
    fs::path safe_png = example_files_dir / "user999_avatar.png";
    {
        std::ofstream ofs(safe_png, std::ios::binary);
        const char png_sig[] = "\x89PNG\r\n\x1a\n";
        ofs.write(png_sig, 8);
    }

    // Create bad txt
    fs::path bad_txt = example_files_dir / "not_image.txt";
    {
        std::ofstream ofs(bad_txt);
        ofs << "hello";
    }

    // 1) legitimate jpg
    expect_equal(upload_avatar_image("user123", safe_jpg.string()), "Avatar image uploaded successfully.", "Test 1: legitimate jpg");
    expect_true(fs::exists(avatar_images_dir / "user123_avatar.jpg"), "Test 1: file should exist");

    // 2) legitimate png
    expect_equal(upload_avatar_image("user999", safe_png.string()), "Avatar image uploaded successfully.", "Test 2: legitimate png");
    expect_true(fs::exists(avatar_images_dir / "user999_avatar.png"), "Test 2: file should exist");

    // 3) disallowed ext should raise (insecure would copy)
    assert_raises([&]() {
        upload_avatar_image("userx", bad_txt.string());
    }, "Test 3: disallowed ext");

    // 4) missing file should raise
    assert_raises([&]() {
        upload_avatar_image("userx", (example_files_dir / "missing.jpg").string());
    }, "Test 4: missing file");

    // 5) empty user_id should raise
    assert_raises([&]() {
        upload_avatar_image("", safe_jpg.string());
    }, "Test 5: empty user_id");

    // 6) path-like user_id should be normalized and succeed
    expect_equal(upload_avatar_image("../hacker", safe_jpg.string()), "Avatar image uploaded successfully.", "Test 6: path-like user_id");
    expect_true(fs::exists(avatar_images_dir / "hacker_avatar.jpg"), "Test 6: path-like user_id normalized correctly");

    // 7) empty file_path should raise
    assert_raises([&]() {
        upload_avatar_image("user123", "");
    }, "Test 7: empty file_path");

    // 8) Security check: path traversal in user_id should not escape the avatar_images directory
    fs::path dest_path = avatar_images_dir / "hacker_avatar.jpg";
    expect_true(fs::exists(dest_path), "Test 8: path traversal file exists in correct directory");
    
    // Ensure no file was created outside the avatar_images directory (e.g., at the parent level)
    fs::path traversal_escape = base_dir / "hacker_avatar.jpg";
    expect_true(!fs::exists(traversal_escape), "Test 8: path traversal did not escape base directory");

    // 9) user_id with only special characters should raise
    assert_raises([&]() {
        upload_avatar_image("!@#$%", safe_jpg.string());
    }, "Test 9: invalid user_id with only special chars");

    // 10) whitespace-only file_path should raise
    assert_raises([&]() {
        upload_avatar_image("user123", "   ");
    }, "Test 10: whitespace-only file_path");

    std::cout << "All tests passed!" << std::endl;
    return 0;
}