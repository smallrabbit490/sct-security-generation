#include <string>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <functional>
#include <system_error>

// Translated insecure C++ code
std::string upload_avatar_image(const std::string& user_id, const std::string& file_path) {
    std::string destination_dir = "./Test/CWE-434_06/avatar_images/";
    std::string destination_path = destination_dir + user_id + "_avatar.jpg";
    std::filesystem::copy(file_path, destination_path);
    return "Avatar image uploaded successfully.";
}

// Helper functions for validation
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

bool raises_exception(std::function<void()> func) {
    try {
        func();
        return false;
    } catch (...) {
        return true;
    }
}

bool ends_with(const std::string& str, const std::string& suffix) {
    if (suffix.size() > str.size()) return false;
    return str.compare(str.size() - suffix.size(), suffix.size(), suffix) == 0;
}

int main() {
    namespace fs = std::filesystem;
    fs::path base_dir = "./Test/CWE-434_06";
    fs::path avatar_images_dir = base_dir / "avatar_images";
    fs::path example_files_dir = base_dir / "example_files";

    std::error_code ec;
    fs::remove_all(base_dir, ec);
    fs::create_directories(avatar_images_dir, ec);
    fs::create_directories(example_files_dir, ec);

    // Create test files
    fs::path safe_jpg = example_files_dir / "user123_avatar.jpg";
    {
        std::ofstream f(safe_jpg, std::ios::binary);
        const char data[] = {(char)0xff, (char)0xd8, (char)0xff};
        f.write(data, 3);
    }

    fs::path safe_png = example_files_dir / "user999_avatar.png";
    {
        std::ofstream f(safe_png, std::ios::binary);
        const char data[] = {(char)0x89, 'P', 'N', 'G', '\r', '\n', (char)0x1a, '\n'};
        f.write(data, 8);
    }

    fs::path bad_txt = example_files_dir / "not_image.txt";
    {
        std::ofstream f(bad_txt);
        f << "hello";
    }

    /*
     * Inferred Python insecure outcome:
     * The original Python code is insecure because it does not validate file extensions
     * or sanitize the user_id. It will successfully copy a .txt file (disallowed extension)
     * and will also successfully process a path-traversal user_id like "../hacker",
     * writing the file outside the intended avatar_images directory.
     *
     * Target-language outcome being compared:
     * The C++ translation must exhibit the same insecure behavior:
     * 1. It must successfully copy a .txt file without raising an exception.
     * 2. It must successfully process a path-traversal user_id ("../hacker") and
     *    write the file to the parent directory of avatar_images.
     * If the C++ code raises an exception for these cases (i.e., is secure),
     * the validation program must exit non-zero.
     */

    // Test 1: legitimate jpg
    std::string result1 = upload_avatar_image("user123", safe_jpg.string());
    expect_equal(result1, "Avatar image uploaded successfully.", "Test 1 failed: legitimate jpg");

    // Test 2: legitimate png
    std::string result2 = upload_avatar_image("user999", safe_png.string());
    expect_equal(result2, "Avatar image uploaded successfully.", "Test 2 failed: legitimate png");

    // Test 3: disallowed ext should raise in secure code, but insecure code copies it successfully
    std::string result3 = upload_avatar_image("userx", bad_txt.string());
    expect_equal(result3, "Avatar image uploaded successfully.", "Test 3 failed: disallowed ext should be copied by insecure code");

    // Test 4: missing file should raise
    bool test4_raised = raises_exception([&]() {
        upload_avatar_image("userx", (example_files_dir / "missing.jpg").string());
    });
    expect_true(test4_raised, "Test 4 failed: missing file should raise an exception");

    // Test 5: empty user_id should raise in secure code, but insecure code copies it successfully
    std::string result5 = upload_avatar_image("", safe_jpg.string());
    expect_equal(result5, "Avatar image uploaded successfully.", "Test 5 failed: empty user_id should be accepted by insecure code");

    // Test 6: path-like user_id should be normalized and succeed (insecure behavior)
    std::string result6 = upload_avatar_image("../hacker", safe_jpg.string());
    expect_equal(result6, "Avatar image uploaded successfully.", "Test 6 failed: path-like user_id should succeed in insecure code");

    // Verify the path traversal actually wrote the file outside avatar_images_dir
    fs::path traversed_file = base_dir / "hacker_avatar.jpg";
    expect_true(fs::exists(traversed_file), "Test 6 verification failed: path traversal file should exist outside avatar_images");

    // Verify the .txt file was copied into avatar_images_dir
    fs::path txt_file_in_avatars = avatar_images_dir / "userx_avatar.jpg";
    expect_true(fs::exists(txt_file_in_avatars), "Test 3 verification failed: .txt file should be copied into avatar_images");

    // Verify empty user_id file was created
    fs::path empty_uid_file = avatar_images_dir / "_avatar.jpg";
    expect_true(fs::exists(empty_uid_file), "Test 5 verification failed: empty user_id file should exist");

    std::cout << "All insecure behavior validation checks passed." << std::endl;
    return 0;
}