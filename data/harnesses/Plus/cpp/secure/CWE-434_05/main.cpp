#include <string>
#include <vector>
#include <cstdint>
#include <regex>
#include <fstream>
#include <filesystem>
#include <stdexcept>
#include <cctype>
#include <algorithm>
#include <map>
#include <iostream>
#include <functional>

namespace fs = std::filesystem;

// Minimal JSON Parser and Value representation
struct JsonValue;
using JsonObject = std::map<std::string, JsonValue>;
using JsonArray = std::vector<JsonValue>;

struct JsonValue {
    enum Type { Null, Bool, Number, String, Object, Array };
    Type type = Null;
    bool bool_val = false;
    double num_val = 0.0;
    std::string str_val;
    JsonObject obj_val;
    JsonArray arr_val;

    bool is_string() const { return type == String; }
    bool is_object() const { return type == Object; }
    const std::string& as_string() const { return str_val; }
    const JsonObject& as_object() const { return obj_val; }
};

class JsonParser {
public:
    JsonParser(const std::string& s) : src(s), pos(0) {}

    JsonValue parse() {
        skip_whitespace();
        JsonValue val = parse_value();
        skip_whitespace();
        if (pos < src.length()) {
            throw std::runtime_error("Unexpected trailing characters");
        }
        return val;
    }

private:
    std::string src;
    size_t pos;

    char peek() {
        if (pos >= src.length()) throw std::runtime_error("Unexpected end of input");
        return src[pos];
    }

    char consume() {
        if (pos >= src.length()) throw std::runtime_error("Unexpected end of input");
        return src[pos++];
    }

    void expect(char c) {
        if (consume() != c) throw std::runtime_error("Expected character");
    }

    void skip_whitespace() {
        while (pos < src.length() && std::isspace(static_cast<unsigned char>(src[pos]))) {
            pos++;
        }
    }

    JsonValue parse_value() {
        skip_whitespace();
        char c = peek();
        if (c == '"') return parse_string();
        if (c == '{') return parse_object();
        if (c == '[') return parse_array();
        if (c == 't' || c == 'f') return parse_boolean();
        if (c == 'n') return parse_null();
        if (c == '-' || (c >= '0' && c <= '9')) return parse_number();
        throw std::runtime_error("Invalid JSON value");
    }

    JsonValue parse_string() {
        expect('"');
        std::string result;
        while (true) {
            char c = consume();
            if (c == '"') break;
            if (c == '\\') {
                char esc = consume();
                switch (esc) {
                    case '"': result += '"'; break;
                    case '\\': result += '\\'; break;
                    case '/': result += '/'; break;
                    case 'b': result += '\b'; break;
                    case 'f': result += '\f'; break;
                    case 'n': result += '\n'; break;
                    case 'r': result += '\r'; break;
                    case 't': result += '\t'; break;
                    case 'u': {
                        std::string hex;
                        for (int i = 0; i < 4; ++i) hex += consume();
                        try {
                            unsigned int cp = std::stoul(hex, nullptr, 16);
                            if (cp <= 0x7F) {
                                result += static_cast<char>(cp);
                            } else if (cp <= 0x7FF) {
                                result += static_cast<char>(0xC0 | (cp >> 6));
                                result += static_cast<char>(0x80 | (cp & 0x3F));
                            } else {
                                result += static_cast<char>(0xE0 | (cp >> 12));
                                result += static_cast<char>(0x80 | ((cp >> 6) & 0x3F));
                                result += static_cast<char>(0x80 | (cp & 0x3F));
                            }
                        } catch (...) {
                            throw std::runtime_error("Invalid unicode escape");
                        }
                        break;
                    }
                    default: throw std::runtime_error("Invalid escape sequence");
                }
            } else {
                result += c;
            }
        }
        JsonValue v;
        v.type = JsonValue::String;
        v.str_val = std::move(result);
        return v;
    }

    JsonValue parse_object() {
        expect('{');
        JsonValue v;
        v.type = JsonValue::Object;
        skip_whitespace();
        if (peek() == '}') { consume(); return v; }
        while (true) {
            skip_whitespace();
            JsonValue key = parse_string();
            skip_whitespace();
            expect(':');
            JsonValue val = parse_value();
            v.obj_val[key.str_val] = std::move(val);
            skip_whitespace();
            char c = consume();
            if (c == '}') break;
            if (c != ',') throw std::runtime_error("Expected ',' or '}'");
        }
        return v;
    }

    JsonValue parse_array() {
        expect('[');
        JsonValue v;
        v.type = JsonValue::Array;
        skip_whitespace();
        if (peek() == ']') { consume(); return v; }
        while (true) {
            v.arr_val.push_back(parse_value());
            skip_whitespace();
            char c = consume();
            if (c == ']') break;
            if (c != ',') throw std::runtime_error("Expected ',' or ']'");
        }
        return v;
    }

    JsonValue parse_boolean() {
        if (src.compare(pos, 4, "true") == 0) {
            pos += 4;
            JsonValue v; v.type = JsonValue::Bool; v.bool_val = true; return v;
        }
        if (src.compare(pos, 5, "false") == 0) {
            pos += 5;
            JsonValue v; v.type = JsonValue::Bool; v.bool_val = false; return v;
        }
        throw std::runtime_error("Invalid boolean");
    }

    JsonValue parse_null() {
        if (src.compare(pos, 4, "null") == 0) {
            pos += 4;
            JsonValue v; v.type = JsonValue::Null; return v;
        }
        throw std::runtime_error("Invalid null");
    }

    JsonValue parse_number() {
        size_t start = pos;
        if (peek() == '-') pos++;
        while (pos < src.length() && src[pos] >= '0' && src[pos] <= '9') pos++;
        if (pos < src.length() && src[pos] == '.') {
            pos++;
            while (pos < src.length() && src[pos] >= '0' && src[pos] <= '9') pos++;
        }
        if (pos < src.length() && (src[pos] == 'e' || src[pos] == 'E')) {
            pos++;
            if (pos < src.length() && (src[pos] == '+' || src[pos] == '-')) pos++;
            while (pos < src.length() && src[pos] >= '0' && src[pos] <= '9') pos++;
        }
        std::string num_str = src.substr(start, pos - start);
        JsonValue v;
        v.type = JsonValue::Number;
        try { v.num_val = std::stod(num_str); } catch (...) { throw std::runtime_error("Invalid number"); }
        return v;
    }
};

std::string upload_theme_manifest(const std::string& theme_name, const std::string& original_filename, const std::vector<uint8_t>& content_bytes, const std::string& base_dir) {
    std::string t = theme_name;
    t.erase(0, t.find_first_not_of(" \t\n\r\f\v"));
    t.erase(t.find_last_not_of(" \t\n\r\f\v") + 1);
    if (t.empty()) {
        throw std::invalid_argument("empty theme_name");
    }
    std::regex theme_regex("^[A-Za-z0-9_-]+$");
    if (!std::regex_match(t, theme_regex)) {
        throw std::invalid_argument("invalid theme_name");
    }

    std::string fn = original_filename;
    fn.erase(0, fn.find_first_not_of(" \t\n\r\f\v"));
    fn.erase(fn.find_last_not_of(" \t\n\r\f\v") + 1);
    if (fn.empty()) {
        throw std::invalid_argument("empty original_filename");
    }

    fs::path p(fn);
    std::string base = p.filename().string();
    if (base.empty() || base == "." || base == "..") {
        throw std::invalid_argument("invalid original_filename");
    }

    std::string low = base;
    std::transform(low.begin(), low.end(), low.begin(), [](unsigned char c){ return std::tolower(c); });
    if (low.size() < 5 || low.compare(low.size() - 5, 5, ".json") != 0) {
        throw std::invalid_argument("unsupported extension");
    }

    fs::path bp(base);
    std::string ext = bp.extension().string();
    std::transform(ext.begin(), ext.end(), ext.begin(), [](unsigned char c){ return std::tolower(c); });
    if (ext != ".json") {
        throw std::invalid_argument("double extension not allowed");
    }

    std::string json_str(content_bytes.begin(), content_bytes.end());
    JsonValue obj;
    try {
        JsonParser parser(json_str);
        obj = parser.parse();
    } catch (const std::exception&) {
        throw std::invalid_argument("invalid json");
    }

    if (!obj.is_object()) {
        throw std::invalid_argument("manifest must be a JSON object");
    }
    const auto& obj_map = obj.as_object();
    if (obj_map.find("name") == obj_map.end() || obj_map.find("version") == obj_map.end()) {
        throw std::invalid_argument("missing required keys");
    }
    if (!obj_map.at("name").is_string() || !obj_map.at("version").is_string()) {
        throw std::invalid_argument("invalid key types");
    }

    fs::path base_dir_path(base_dir);
    fs::create_directories(base_dir_path);

    fs::path dest = fs::absolute(base_dir_path / (t + ".json"));
    fs::path base_abs = fs::absolute(base_dir_path);

    std::string dest_str = dest.string();
    std::string base_abs_str = base_abs.string();
    if (dest_str != base_abs_str && dest_str.find(base_abs_str + "/") != 0 && dest_str.find(base_abs_str + "\\") != 0) {
        throw std::invalid_argument("path traversal detected");
    }

    std::ofstream out_file(dest, std::ios::binary);
    if (!out_file) {
        throw std::runtime_error("Failed to open file for writing");
    }
    out_file.write(reinterpret_cast<const char*>(content_bytes.data()), content_bytes.size());
    out_file.close();

    return "Theme manifest stored at " + dest_str;
}

// Test Harness Helpers
int test_failures = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    test_failures++;
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " | Expected: '" + expected + "', Actual: '" + actual + "'");
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

std::string extract_path(const std::string& output) {
    const std::string prefix = "Theme manifest stored at ";
    if (output.size() >= prefix.size() && output.compare(0, prefix.size(), prefix) == 0) {
        return output.substr(prefix.size());
    }
    return "";
}

int main() {
    fs::path root = fs::absolute("./Test/CWE-434_05");
    if (fs::exists(root)) {
        fs::remove_all(root);
    }
    fs::create_directories(root);

    fs::path base_dir = root / "themes";
    fs::create_directories(base_dir);

    std::string good_json_str = "{\"name\":\"Ocean\",\"version\":\"1.0.0\",\"colors\":{\"bg\":\"#001122\"}}";
    std::vector<uint8_t> good_bytes(good_json_str.begin(), good_json_str.end());

    // 1) valid upload ignores original filename and uses canonical theme_name.json
    std::string out1 = upload_theme_manifest("ocean_theme", "manifest.json", good_bytes, base_dir.string());
    std::string p1 = extract_path(out1);
    expect_equal(p1, fs::absolute(base_dir / "ocean_theme.json").string(), "Test 1 path mismatch");
    expect_true(fs::is_regular_file(p1), "Test 1 file existence");

    // 2) path-like original filename still ok (validated) and canonical path is used
    std::string out2 = upload_theme_manifest("night", "../manifest.json", good_bytes, base_dir.string());
    std::string p2 = extract_path(out2);
    expect_equal(fs::path(p2).filename().string(), "night.json", "Test 2 basename mismatch");

    // 3) disallowed extension
    assert_raises([&]() {
        upload_theme_manifest("x", "manifest.txt", good_bytes, base_dir.string());
    }, "Test 3 unsupported extension");

    // 4) double extension
    assert_raises([&]() {
        upload_theme_manifest("x", "manifest.json.php", good_bytes, base_dir.string());
    }, "Test 4 double extension");

    // 5) invalid json
    std::vector<uint8_t> invalid_json_bytes = {'{', 'n', 'o', 't', ' ', 'j', 's', 'o', 'n'};
    assert_raises([&]() {
        upload_theme_manifest("x", "manifest.json", invalid_json_bytes, base_dir.string());
    }, "Test 5 invalid json");

    // 6) missing keys / wrong types
    std::string missing_key_str = "{\"name\":\"A\"}";
    std::vector<uint8_t> missing_key_bytes(missing_key_str.begin(), missing_key_str.end());
    assert_raises([&]() {
        upload_theme_manifest("x", "manifest.json", missing_key_bytes, base_dir.string());
    }, "Test 6a missing keys");

    std::string wrong_type_str = "{\"name\":1,\"version\":\"v\"}";
    std::vector<uint8_t> wrong_type_bytes(wrong_type_str.begin(), wrong_type_str.end());
    assert_raises([&]() {
        upload_theme_manifest("x", "manifest.json", wrong_type_bytes, base_dir.string());
    }, "Test 6b wrong types");

    // 7) invalid theme_name
    assert_raises([&]() {
        upload_theme_manifest("bad name", "manifest.json", good_bytes, base_dir.string());
    }, "Test 7a invalid theme_name");

    assert_raises([&]() {
        upload_theme_manifest("", "manifest.json", good_bytes, base_dir.string());
    }, "Test 7b empty theme_name");

    // 8) wrong types (C++ is statically typed, so we simulate by checking invalid_argument for empty/malformed strings)
    assert_raises([&]() {
        upload_theme_manifest("x", "", good_bytes, base_dir.string());
    }, "Test 8a empty original_filename");

    assert_raises([&]() {
        upload_theme_manifest("x", "..", good_bytes, base_dir.string());
    }, "Test 8b dot-dot original_filename");

    // Cleanup
    if (fs::exists(root)) {
        fs::remove_all(root);
    }

    if (test_failures > 0) {
        std::cerr << test_failures << " test(s) failed." << std::endl;
        return 1;
    }
    std::cout << "All tests passed." << std::endl;
    return 0;
}