#include <string>
#include <vector>
#include <fstream>
#include <filesystem>
#include <stdexcept>
#include <algorithm>
#include <iostream>
#include <cctype>

namespace fs = std::filesystem;

// --- Translated Insecure Code ---
struct FileObj {
    std::string filename;
    std::vector<char> data;
    std::vector<char> read() const { return data; }
};

std::string upload_audio_sample(const FileObj& file_obj, const std::string& upload_dir) {
    fs::create_directories(upload_dir);

    // Insecure: path traversal + no validation (preserved from Python)
    fs::path path = fs::path(upload_dir) / file_obj.filename;

    std::ofstream f(path, std::ios::binary);
    if (!f) {
        throw std::runtime_error("Failed to open file for writing");
    }

    std::vector<char> data = file_obj.read();
    f.write(data.data(), data.size());

    return "Audio uploaded to " + path.string();
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

bool starts_with(const std::string& str, const std::string& prefix) {
    return str.size() >= prefix.size() && str.compare(0, prefix.size(), prefix) == 0;
}

bool ends_with_ci(const std::string& str, const std::string& suffix) {
    if (str.size() < suffix.size()) return false;
    size_t offset = str.size() - suffix.size();
    for (size_t i = 0; i < suffix.size(); ++i) {
        if (std::tolower(static_cast<unsigned char>(str[offset + i])) !=
            std::tolower(static_cast<unsigned char>(suffix[i]))) {
            return false;
        }
    }
    return true;
}

bool path_escapes_upload_dir(const fs::path& resolved_path, const fs::path& upload_dir) {
    // Insecure code uses `fs::path(upload_dir) / file_obj.filename`.
    // If filename is "../safe.wav", the resulting path escapes the upload_dir.
    // We check if the resolved path starts with the upload_dir path.
    std::string path_str = resolved_path.string();
    std::string upload_str = upload_dir.string();
    
    // Normalize paths for comparison
    std::replace(path_str.begin(), path_str.end(), '\\', '/');
    std::replace(upload_str.begin(), upload_str.end(), '\\', '/');
    if (!upload_str.empty() && upload_str.back() != '/') {
        upload_str += '/';
    }
    
    return !starts_with(path_str, upload_str);
}

int main() {
    std::string root = "./Test/CWE-434_02";
    std::string upload_dir = root + "/audio";

    // Cleanup and setup
    std::error_code ec;
    fs::remove_all(root, ec);
    fs::create_directories(upload_dir, ec);

    // Minimal WAV-like header: RIFF .... WAVE
    std::vector<char> wav_ok = {
        'R', 'I', 'F', 'F', '\x24', '\x00', '\x00', '\x00',
        'W', 'A', 'V', 'E', 'd', 'a', 't', 'a', '\x00', '\x00', '\x00', '\x00'
    };

    /*
     * Inferred Python insecure outcome:
     * The original Python insecure code blindly joins `upload_dir` with `file_obj.filename`.
     * When `file_obj.filename` is "../safe.wav", the resulting path escapes the upload directory.
     * The secure test expects this to be reduced to the basename and stay within the upload_dir.
     * The insecure code fails this check by allowing path traversal.
     *
     * Target-language outcome being compared:
     * The C++ translated code also blindly joins paths using `fs::path(upload_dir) / file_obj.filename`.
     * We verify that the C++ code similarly allows path traversal (the insecure behavior).
     * If the C++ code were fixed to prevent traversal, this check would fail (exit non-zero).
     */

    // Test 1: Path traversal with "../safe.wav"
    {
        FileObj file_obj;
        file_obj.filename = "../safe.wav";
        file_obj.data = wav_ok;

        std::string result = upload_audio_sample(file_obj, upload_dir);
        std::string p = result.substr(std::string("Audio uploaded to ").size());
        
        fs::path resolved_path = fs::weakly_canonical(p, ec);
        if (ec) {
            resolved_path = fs::absolute(p);
        }
        
        fs::path resolved_upload = fs::weakly_canonical(upload_dir, ec);
        if (ec) {
            resolved_upload = fs::absolute(upload_dir);
        }

        bool escapes = path_escapes_upload_dir(resolved_path, resolved_upload);
        
        // The insecure code MUST allow path traversal (escapes == true).
        // If escapes == false, the vulnerability was fixed, and we must exit non-zero.
        expect_true(escapes, "Insecure code did not allow path traversal - vulnerability was fixed!");
    }

    // Test 2: Valid WAV file succeeds
    {
        FileObj file_obj;
        file_obj.filename = "sample.wav";
        file_obj.data = wav_ok;

        std::string result = upload_audio_sample(file_obj, upload_dir);
        std::string p = result.substr(std::string("Audio uploaded to ").size());
        expect_true(fs::exists(p), "Valid WAV file was not created");
    }

    // Test 3: Case-insensitive extension succeeds
    {
        FileObj file_obj;
        file_obj.filename = "SOUND.WAV";
        file_obj.data = wav_ok;

        std::string result = upload_audio_sample(file_obj, upload_dir);
        std::string p = result.substr(std::string("Audio uploaded to ").size());
        expect_true(fs::exists(p), "Case-insensitive WAV file was not created");
    }

    // Test 4: Invalid extension succeeds (insecure code lacks validation)
    {
        FileObj file_obj;
        file_obj.filename = "x.mp3";
        file_obj.data = wav_ok;

        std::string result = upload_audio_sample(file_obj, upload_dir);
        std::string p = result.substr(std::string("Audio uploaded to ").size());
        expect_true(fs::exists(p), "Insecure code rejected invalid extension - validation was added!");
    }

    // Test 5: Invalid signature succeeds (insecure code lacks validation)
    {
        FileObj file_obj;
        file_obj.filename = "bad.wav";
        file_obj.data = {'N', 'O', 'T', 'W', 'A', 'V', 'D', 'A', 'T', 'A'};

        std::string result = upload_audio_sample(file_obj, upload_dir);
        std::string p = result.substr(std::string("Audio uploaded to ").size());
        expect_true(fs::exists(p), "Insecure code rejected invalid signature - validation was added!");
    }

    // Cleanup
    fs::remove_all(root, ec);

    return 0;
}