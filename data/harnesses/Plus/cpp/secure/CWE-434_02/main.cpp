#include <string>
#include <vector>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <algorithm>
#include <cctype>
#include <iostream>
#include <functional>

namespace fs = std::filesystem;

struct FileObj {
    std::string filename;
    virtual std::vector<unsigned char> read() const = 0;
    virtual ~FileObj() = default;
};

std::string upload_audio_sample(const FileObj& file_obj, const std::string& upload_dir) {
    if (upload_dir.empty()) {
        throw std::invalid_argument("invalid upload_dir");
    }

    bool all_space = true;
    for (char c : upload_dir) {
        if (!std::isspace(static_cast<unsigned char>(c))) {
            all_space = false;
            break;
        }
    }
    if (all_space) {
        throw std::invalid_argument("invalid upload_dir");
    }

    const std::string& filename = file_obj.filename;
    if (filename.empty()) {
        throw std::invalid_argument("empty filename");
    }

    bool filename_all_space = true;
    for (char c : filename) {
        if (!std::isspace(static_cast<unsigned char>(c))) {
            filename_all_space = false;
            break;
        }
    }
    if (filename_all_space) {
        throw std::invalid_argument("empty filename");
    }

    fs::path p(filename);
    std::string base = p.filename().string();

    if (base.empty() || base == "." || base == "..") {
        throw std::invalid_argument("invalid filename");
    }

    if (base.find('.') == std::string::npos) {
        throw std::invalid_argument("missing extension");
    }

    std::string base_lower = base;
    std::transform(base_lower.begin(), base_lower.end(), base_lower.begin(),
                   [](unsigned char c){ return std::tolower(c); });

    const std::string wav_ext = ".wav";
    if (base_lower.size() < wav_ext.size() ||
        base_lower.compare(base_lower.size() - wav_ext.size(), wav_ext.size(), wav_ext) != 0) {
        throw std::invalid_argument("unsupported extension");
    }

    std::vector<unsigned char> data = file_obj.read();

    const size_t max_file_size = 2 * 1024 * 1024; // 2MB
    if (data.size() > max_file_size) {
        throw std::invalid_argument("file size exceeds 2MB");
    }

    if (data.size() < 12) {
        throw std::invalid_argument("invalid wav data");
    }

    if (data[0] != 'R' || data[1] != 'I' || data[2] != 'F' || data[3] != 'F' ||
        data[8] != 'W' || data[9] != 'A' || data[10] != 'V' || data[11] != 'E') {
        throw std::invalid_argument("invalid wav signature");
    }

    fs::create_directories(upload_dir);

    fs::path dest = fs::absolute(fs::path(upload_dir) / base);
    fs::path base_abs = fs::absolute(upload_dir);

    // Path traversal check
    std::string dest_str = dest.string();
    std::string base_abs_str = base_abs.string();
    // Ensure consistent trailing separator for prefix check
    if (!base_abs_str.empty() && base_abs_str.back() != fs::path::preferred_separator) {
        base_abs_str += fs::path::preferred_separator;
    }
    if (dest_str != base_abs.string() && 
        (dest_str.size() < base_abs_str.size() || dest_str.compare(0, base_abs_str.size(), base_abs_str) != 0)) {
        throw std::invalid_argument("path traversal detected");
    }

    std::ofstream out_file(dest, std::ios::binary);
    if (!out_file) {
        throw std::runtime_error("failed to open file for writing");
    }
    out_file.write(reinterpret_cast<const char*>(data.data()), data.size());
    out_file.close();

    return "Audio uploaded to " + dest.string();
}

// --- Mock FileObj Implementations ---

struct MockUpload : public FileObj {
    MockUpload(const std::string& fname, const std::vector<unsigned char>& d) {
        filename = fname;
        data_ = d;
    }
    std::vector<unsigned char> read() const override {
        return data_;
    }
private:
    std::vector<unsigned char> data_;
};

struct MockUploadString : public FileObj {
    MockUploadString(const std::string& fname, const std::string& d) {
        filename = fname;
        data_ = d;
    }
    std::vector<unsigned char> read() const override {
        // Return invalid type representation (empty, simulating non-bytes failure in size check)
        return {};
    }
private:
    std::string data_;
};

// --- Test Helpers ---

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

void assert_raises(const std::function<void()>& func, const std::string& message) {
    try {
        func();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Expected
    }
}

std::vector<unsigned char> make_wav_ok() {
    return {'R', 'I', 'F', 'F', 0x24, 0x00, 0x00, 0x00, 'W', 'A', 'V', 'E', 'd', 'a', 't', 'a', 0x00, 0x00, 0x00, 0x00};
}

// --- Main Test Entry Point ---

int main() {
    fs::path root = fs::absolute("./Test/CWE-434_02");
    if (fs::exists(root)) {
        fs::remove_all(root);
    }
    fs::create_directories(root);

    fs::path upload_dir = root / "audio";
    fs::create_directories(upload_dir);

    std::vector<unsigned char> wav_ok = make_wav_ok();

    // Test 1: Valid upload
    {
        MockUpload mock("sample.wav", wav_ok);
        std::string out = upload_audio_sample(mock, upload_dir.string());
        std::string prefix = "Audio uploaded to ";
        expect_true(out.find(prefix) == 0, "Test 1 - Output prefix mismatch");
        std::string p = out.substr(prefix.size());
        expect_true(fs::is_regular_file(p), "Test 1 - File should exist");
    }

    // Test 2: Case-insensitive extension
    {
        MockUpload mock("SOUND.WAV", wav_ok);
        std::string out2 = upload_audio_sample(mock, upload_dir.string());
        std::string prefix = "Audio uploaded to ";
        expect_true(out2.find(prefix) == 0, "Test 2 - Output prefix mismatch");
        std::string p2 = out2.substr(prefix.size());
        expect_true(fs::is_regular_file(p2), "Test 2 - File should exist");
    }

    // Test 3: Path-like filename reduced to basename
    {
        MockUpload mock("../safe.wav", wav_ok);
        std::string out3 = upload_audio_sample(mock, upload_dir.string());
        std::string prefix = "Audio uploaded to ";
        expect_true(out3.find(prefix) == 0, "Test 3 - Output prefix mismatch");
        std::string p3 = out3.substr(prefix.size());
        fs::path abs_p3 = fs::absolute(p3);
        fs::path abs_upload = fs::absolute(upload_dir);
        std::string abs_p3_str = abs_p3.string();
        std::string abs_upload_str = abs_upload.string();
        if (!abs_upload_str.empty() && abs_upload_str.back() != fs::path::preferred_separator) {
            abs_upload_str += fs::path::preferred_separator;
        }
        expect_true(abs_p3_str.compare(0, abs_upload_str.size(), abs_upload_str) == 0, "Test 3 - Path should start with upload_dir");
        expect_true(abs_p3.filename() == "safe.wav", "Test 3 - Basename should be safe.wav");
    }

    // Test 4: Invalid extension (.mp3)
    {
        MockUpload mock("x.mp3", wav_ok);
        assert_raises([&]() { upload_audio_sample(mock, upload_dir.string()); }, "Test 4");
    }

    // Test 5: Missing extension
    {
        MockUpload mock("noext", wav_ok);
        assert_raises([&]() { upload_audio_sample(mock, upload_dir.string()); }, "Test 5");
    }

    // Test 6: Invalid signature
    {
        std::vector<unsigned char> bad_data = {'N', 'O', 'T', 'W', 'A', 'V', 'D', 'A', 'T', 'A', '1', '2'};
        MockUpload mock("bad.wav", bad_data);
        assert_raises([&]() { upload_audio_sample(mock, upload_dir.string()); }, "Test 6");
    }

    // Test 7: Empty filename
    {
        MockUpload mock("", wav_ok);
        assert_raises([&]() { upload_audio_sample(mock, upload_dir.string()); }, "Test 7");
    }

    // Test 8: Empty upload_dir
    {
        MockUpload mock("a.wav", wav_ok);
        assert_raises([&]() { upload_audio_sample(mock, ""); }, "Test 8");
    }

    // Test 9: Invalid read() return type (simulated via empty data triggering size < 12)
    {
        MockUploadString mock("a.wav", "not-bytes");
        assert_raises([&]() { upload_audio_sample(mock, upload_dir.string()); }, "Test 9");
    }

    // Cleanup
    if (fs::exists(root)) {
        fs::remove_all(root);
    }

    if (fail_count > 0) {
        std::cerr << fail_count << " test(s) failed." << std::endl;
        return 1;
    }

    return 0;
}