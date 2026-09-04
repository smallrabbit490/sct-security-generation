#include <string>
#include <vector>
#include <fstream>
#include <filesystem>
#include <regex>
#include <algorithm>
#include <stdexcept>
#include <cctype>
#include <iostream>
#include <functional>

namespace fs = std::filesystem;

// Minimal JSON parser to validate structure and extract string values
class JsonParser {
public:
    JsonParser(const std::string& s) : str(s), pos(0) {}

    void parse_object() {
        skip_whitespace();
        expect('{');
        skip_whitespace();
        
        bool found_name = false;
        bool found_version = false;

        if (peek() != '}') {
            while (true) {
                skip_whitespace();
                std::string key = parse_string();
                skip_whitespace();
                expect(':');
                skip_whitespace();
                
                if (key == "name") {
                    if (found_name) throw std::runtime_error("Duplicate key 'name'");
                    name_val = parse_string();
                    found_name = true;
                } else if (key == "version") {
                    if (found_version) throw std::runtime_error("Duplicate key 'version'");
                    version_val = parse_string();
                    found_version = true;
                } else {
                    skip_value();
                }
                
                skip_whitespace();
                if (peek() == '}') break;
                expect(',');
                skip_whitespace();
            }
        }
        
        expect('}');
        
        if (!found_name || !found_version) {
            throw std::runtime_error("Missing required keys 'name' and/or 'version'");
        }
    }

    std::string name_val;
    std::string version_val;

private:
    std::string str;
    size_t pos;

    char peek() {
        return pos < str.size() ? str[pos] : '\0';
    }

    char get() {
        return pos < str.size() ? str[pos++] : '\0';
    }

    void skip_whitespace() {
        while (pos < str.size() && std::isspace(static_cast<unsigned char>(str[pos]))) pos++;
    }

    void expect(char c) {
        if (get() != c) throw std::runtime_error("Invalid JSON format");
    }

    std::string parse_string() {
        expect('"');
        std::string result;
        while (peek() != '"') {
            if (peek() == '\0') throw std::runtime_error("Unterminated string");
            char c = get();
            if (c == '\\') {
                if (peek() == '\0') throw std::runtime_error("Unterminated escape");
                result += get();
            } else {
                result += c;
            }
        }
        expect('"');
        return result;
    }

    void skip_value() {
        skip_whitespace();
        char c = peek();
        if (c == '"') {
            parse_string();
        } else if (c == '{') {
            expect('{');
            skip_whitespace();
            if (peek() != '}') {
                while (true) {
                    skip_whitespace();
                    parse_string();
                    skip_whitespace();
                    expect(':');
                    skip_value();
                    skip_whitespace();
                    if (peek() == '}') break;
                    expect(',');
                }
            }
            expect('}');
        } else if (c == '[') {
            expect('[');
            skip_whitespace();
            if (peek() != ']') {
                while (true) {
                    skip_value();
                    skip_whitespace();
                    if (peek() == ']') break;
                    expect(',');
                }
            }
            expect(']');
        } else if (c == 't') {
            for (int i = 0; i < 4; ++i) get();
        } else if (c == 'f') {
            for (int i = 0; i < 5; ++i) get();
        } else if (c == 'n') {
            for (int i = 0; i < 4; ++i) get();
        } else {
            while (pos < str.size() && std::string("-0123456789eE.").find(str[pos]) != std::string::npos) {
                pos++;
            }
        }
    }
};

std::string upload_theme_manifest(const std::string& theme_name, const std::string& original_filename, const std::vector<unsigned char>& content_bytes, const std::string& base_dir) {
    // Validate theme_name
    std::regex theme_regex("^[A-Za-z0-9_-]+$");
    if (!std::regex_match(theme_name, theme_regex)) {
        throw std::runtime_error("Invalid theme name");
    }

    // Extract just the filename part to check extensions
    fs::path filepath(original_filename);
    std::string filename_only = filepath.filename().string();
    
    // Validate extension
    std::string lower_filename = filename_only;
    std::transform(lower_filename.begin(), lower_filename.end(), lower_filename.begin(),
                   [](unsigned char c){ return std::tolower(c); });

    if (lower_filename.size() < 6 || lower_filename.substr(lower_filename.size() - 5) != ".json") {
        throw std::runtime_error("Only JSON manifests are allowed");
    }

    // Reject double extensions
    size_t dot_pos = lower_filename.rfind('.', lower_filename.size() - 6);
    if (dot_pos != std::string::npos) {
        throw std::runtime_error("Double extensions are not allowed");
    }

    // Validate content size
    if (content_bytes.size() > 65536) {
        throw std::runtime_error("Content exceeds 64KB limit");
    }

    // Parse JSON and validate keys
    std::string json_str(content_bytes.begin(), content_bytes.end());
    JsonParser parser(json_str);
    parser.parse_object();

    // Insecure: trusts user filename and content
    fs::path base = base_dir;
    if (base.is_relative()) {
        base = fs::current_path() / base;
    }
    fs::create_directories(base);
    fs::path dst = base / original_filename;

    std::ofstream out(dst, std::ios::binary);
    if (!out) {
        throw std::runtime_error("Failed to open file for writing");
    }
    out.write(reinterpret_cast<const char*>(content_bytes.data()), content_bytes.size());

    return "Theme manifest stored at " + dst.string();
}

// --- Validation Harness Helpers ---

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
        std::cerr << "FAIL: " << message << std::endl;
        std::cerr << "  Expected: " << expected << std::endl;
        std::cerr << "  Actual:   " << actual << std::endl;
        std::exit(1);
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Expected exception
    }
}

// --- Main Validation Entry Point ---

int main() {
    std::string root = "./Test/CWE-434_05";
    std::string base_dir = root + "/themes";

    // Clean up and set up directory
    std::error_code ec;
    fs::remove_all(root, ec);
    fs::create_directories(base_dir, ec);

    std::string good_json_str = "{\"name\":\"Ocean\",\"version\":\"1.0.0\",\"colors\":{\"bg\":\"#001122\"}}";
    std::vector<unsigned char> good_bytes(good_json_str.begin(), good_json_str.end());

    /*
     * Inferred Python insecure outcome:
     * The original Python code is insecure because it uses the user-provided `original_filename` 
     * directly in the destination path (`os.path.join(base_dir, original_filename)`), allowing 
     * path traversal (e.g., "../manifest.json"). The secure specification requires saving the 
     * file as `<theme_name>.json` inside `base_dir`, ignoring the original filename except for 
     * validation. The insecure Python code will write to a traversed path and return that path.
     *
     * Target-language outcome being compared:
     * The C++ translation also uses `original_filename` directly in the destination path 
     * (`fs::path dst = base / original_filename;`). We validate that this insecure behavior 
     * is present: the function succeeds and returns a path that reflects the traversal, 
     * rather than the secure canonical path `<theme_name>.json`.
     */

    // Test 1: Valid upload ignores original filename and uses canonical theme_name.json
    // Secure behavior: path should be <base_dir>/ocean_theme.json
    // Insecure behavior: path will be <base_dir>/manifest.json
    std::string out1 = upload_theme_manifest("ocean_theme", "manifest.json", good_bytes, base_dir);
    std::string p1 = out1.substr(std::string("Theme manifest stored at ").length());
    
    fs::path expected_secure_path1 = fs::absolute(base_dir) / "ocean_theme.json";
    fs::path actual_path1 = fs::weakly_canonical(p1);
    
    // If the code were secure, p1 would equal expected_secure_path1. 
    // We check that it does NOT equal the secure path (proving the vulnerability exists).
    if (actual_path1 == fs::weakly_canonical(expected_secure_path1.string())) {
        fail("Test 1 failed: Code appears to be secure (used canonical theme_name.json), but insecure behavior was expected.");
    }
    
    // Verify the insecure path was actually created
    expect_true(fs::exists(actual_path1), "Test 1 failed: Insecure path was not created on disk.");


    // Test 2: Path-like original filename still ok (validated) and canonical path is used
    // Secure behavior: path should be <base_dir>/night.json
    // Insecure behavior: path will be <base_dir>/../manifest.json (traversal)
    std::string out2 = upload_theme_manifest("night", "../manifest.json", good_bytes, base_dir);
    std::string p2 = out2.substr(std::string("Theme manifest stored at ").length());
    
    fs::path expected_secure_path2 = fs::absolute(base_dir) / "night.json";
    fs::path actual_path2 = fs::weakly_canonical(p2);
    
    // Check that the secure path was NOT used
    if (actual_path2 == fs::weakly_canonical(expected_secure_path2.string())) {
        fail("Test 2 failed: Code appears to be secure (used canonical night.json), but insecure behavior was expected.");
    }
    
    // Check that the basename of the insecure path is NOT night.json
    expect_true(actual_path2.filename().string() != "night.json", "Test 2 failed: Path basename was night.json, expected manifest.json from traversal.");


    // Test 3: Disallowed extension
    assert_raises([]() {
        std::string good_json_str = "{\"name\":\"Ocean\",\"version\":\"1.0.0\"}";
        std::vector<unsigned char> good_bytes(good_json_str.begin(), good_json_str.end());
        upload_theme_manifest("x", "manifest.txt", good_bytes, "./Test/CWE-434_05/themes");
    }, "Test 3 failed: Disallowed extension should raise exception");


    // Test 4: Double extension
    assert_raises([]() {
        std::string good_json_str = "{\"name\":\"Ocean\",\"version\":\"1.0.0\"}";
        std::vector<unsigned char> good_bytes(good_json_str.begin(), good_json_str.end());
        upload_theme_manifest("x", "manifest.json.php", good_bytes, "./Test/CWE-434_05/themes");
    }, "Test 4 failed: Double extension should raise exception");


    // Test 5: Invalid JSON
    assert_raises([]() {
        std::vector<unsigned char> bad_json = {'{', 'n', 'o', 't', ' ', 'j', 's', 'o', 'n'};
        upload_theme_manifest("x", "manifest.json", bad_json, "./Test/CWE-434_05/themes");
    }, "Test 5 failed: Invalid JSON should raise exception");


    // Test 6: Missing keys / wrong types
    assert_raises([]() {
        std::string json_str = "{\"name\":\"A\"}";
        std::vector<unsigned char> bytes(json_str.begin(), json_str.end());
        upload_theme_manifest("x", "manifest.json", bytes, "./Test/CWE-434_05/themes");
    }, "Test 6a failed: Missing keys should raise exception");

    assert_raises([]() {
        std::string json_str = "{\"name\":1,\"version\":\"v\"}";
        std::vector<unsigned char> bytes(json_str.begin(), json_str.end());
        upload_theme_manifest("x", "manifest.json", bytes, "./Test/CWE-434_05/themes");
    }, "Test 6b failed: Wrong types should raise exception");


    // Test 7: Invalid theme_name
    assert_raises([]() {
        std::string good_json_str = "{\"name\":\"Ocean\",\"version\":\"1.0.0\"}";
        std::vector<unsigned char> good_bytes(good_json_str.begin(), good_json_str.end());
        upload_theme_manifest("bad name", "manifest.json", good_bytes, "./Test/CWE-434_05/themes");
    }, "Test 7a failed: Invalid theme name should raise exception");

    assert_raises([]() {
        std::string good_json_str = "{\"name\":\"Ocean\",\"version\":\"1.0.0\"}";
        std::vector<unsigned char> good_bytes(good_json_str.begin(), good_json_str.end());
        upload_theme_manifest("", "manifest.json", good_bytes, "./Test/CWE-434_05/themes");
    }, "Test 7b failed: Empty theme name should raise exception");

    // Cleanup
    fs::remove_all(root, ec);

    std::cout << "All validation checks passed." << std::endl;
    return 0;
}