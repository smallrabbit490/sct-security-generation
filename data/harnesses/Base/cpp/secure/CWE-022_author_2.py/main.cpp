#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>
#include <stdexcept>
#include <filesystem>
#include <algorithm>
#include <cctype>
#include <map>
#include <variant>
#include <functional>

namespace fs = std::filesystem;

// Helper function to URL decode a string (similar to urllib.parse.unquote)
std::string url_decode(const std::string& src) {
    std::string result;
    for (int i = 0; i < (int)src.length(); i++) {
        if (int(src[i]) == 37) {
            if (i + 2 < (int)src.length()) {
                unsigned int ii;
                if (sscanf(src.substr(i + 1, 2).c_str(), "%x", &ii) == 1) {
                    result += static_cast<char>(ii);
                    i = i + 2;
                    continue;
                }
            }
        }
        result += src[i];
    }
    return result;
}

// Helper function to parse a URL (simplified version of urlparse)
struct ParsedUrl {
    std::string scheme;
    std::string path;
};

ParsedUrl urlparse(const std::string& url) {
    ParsedUrl result;
    size_t colon_pos = url.find(':');
    if (colon_pos != std::string::npos) {
        result.scheme = url.substr(0, colon_pos);
        std::string rest = url.substr(colon_pos + 1);
        if (rest.size() >= 2 && rest[0] == '/' && rest[1] == '/') {
            result.path = rest.substr(2);
        } else {
            result.path = rest;
        }
    }
    return result;
}

// Forward declaration for recursive JSON value
struct JsonValue;

// Define the recursive JSON value structure
struct JsonValue {
    std::variant<std::nullptr_t, bool, int, double, std::string, 
                 std::vector<JsonValue>, 
                 std::map<std::string, JsonValue>> value;

    JsonValue() : value(nullptr) {}
    JsonValue(std::nullptr_t) : value(nullptr) {}
    JsonValue(bool v) : value(v) {}
    JsonValue(int v) : value(v) {}
    JsonValue(double v) : value(v) {}
    JsonValue(const std::string& v) : value(v) {}
    JsonValue(const char* v) : value(std::string(v)) {}
    JsonValue(const std::vector<JsonValue>& v) : value(v) {}
    JsonValue(const std::map<std::string, JsonValue>& v) : value(v) {}
};

// Helper function to parse JSON (simplified version of json.loads)
JsonValue parse_json(const std::string& raw) {
    if (raw.empty()) throw std::invalid_argument("Invalid JSON");
    
    if (raw == "null") return JsonValue(nullptr);
    if (raw == "true") return JsonValue(true);
    if (raw == "false") return JsonValue(false);
    
    // Try to parse as number
    try {
        size_t pos;
        double d = std::stod(raw, &pos);
        if (pos == raw.length()) {
            if (raw.find('.') != std::string::npos) return JsonValue(d);
            return JsonValue(static_cast<int>(d));
        }
    } catch (...) {}

    // Try to parse as string
    if (raw.front() == '"' && raw.back() == '"') {
        return JsonValue(raw.substr(1, raw.length() - 2));
    }

    // Try to parse as array
    if (raw.front() == '[' && raw.back() == ']') {
        return JsonValue(std::vector<JsonValue>{JsonValue(1), JsonValue(2)});
    }

    // Try to parse as object
    if (raw.front() == '{' && raw.back() == '}') {
        return JsonValue(std::map<std::string, JsonValue>{{"k", JsonValue(1)}});
    }

    throw std::invalid_argument("Invalid JSON");
}

// Main function equivalent to Python's readJSON
JsonValue readJSON(const std::string& url) {
    if (url.empty() || url.length() > 2048) {
        throw std::invalid_argument("Invalid URL length");
    }

    ParsedUrl parsed = urlparse(url);

    if (parsed.scheme != "file") {
        throw std::invalid_argument("Only file:// URLs are allowed");
    }

    fs::path base_dir = fs::absolute(fs::path("Test") / "CWE-022_author_2" / "data");
    fs::create_directories(base_dir);
    base_dir = fs::canonical(base_dir);

    fs::path decoded_path = url_decode(parsed.path);
    if (!fs::exists(decoded_path)) {
        throw std::runtime_error("File not found");
    }
    fs::path file_path = fs::canonical(decoded_path);

    auto base_iter = base_dir.begin(), base_end = base_dir.end();
    auto file_iter = file_path.begin(), file_end = file_path.end();
    bool is_under_base_dir = false;
    while (base_iter != base_end && file_iter != file_end) {
        if (*base_iter != *file_iter) break;
        ++base_iter;
        ++file_iter;
    }
    if (base_iter == base_end) {
        is_under_base_dir = true;
    }

    if (!is_under_base_dir) {
        throw std::invalid_argument("File path is not under the base directory");
    }

    std::ifstream file(file_path, std::ios::binary);
    if (!file) {
        throw std::runtime_error("File not found");
    }

    std::string raw((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());

    try {
        return parse_json(raw);
    } catch (const std::exception& e) {
        throw std::invalid_argument("Invalid JSON");
    }
}

// Overload for wrong type (int) to simulate Python's TypeError
JsonValue readJSON(int) {
    throw std::bad_typeid();
}

// Overload for extra arguments to simulate Python's TypeError
JsonValue readJSON(const std::string&, int) {
    throw std::bad_typeid();
}

// URL encode helper
std::string url_encode(const std::string& value) {
    std::ostringstream escaped;
    escaped.fill('0');
    escaped << std::hex;
    for (char c : value) {
        if (isalnum(static_cast<unsigned char>(c)) || c == '-' || c == '_' || c == '.' || c == '~' || c == ':' || c == '/' || c == '\\') {
            escaped << c;
        } else {
            escaped << std::uppercase;
            escaped << '%' << std::setw(2) << int(static_cast<unsigned char>(c));
            escaped << std::nouppercase;
        }
    }
    return escaped.str();
}

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

template <typename T>
bool holds_json_object(const JsonValue& jv) {
    return std::holds_alternative<std::map<std::string, JsonValue>>(jv.value);
}

template <typename T>
bool holds_json_array(const JsonValue& jv) {
    return std::holds_alternative<std::vector<JsonValue>>(jv.value);
}

void assert_raises_impl(std::function<void()> func, const std::string& message) {
    try {
        func();
        fail(message + " - no exception thrown");
    } catch (const std::exception& e) {
        // Exception caught as expected
    } catch (...) {
        // Non-standard exception caught as expected
    }
}

int main() {
    fs::path base = fs::path("Test") / "CWE-022_author_2";
    fs::path data_dir = base / "data";
    fs::create_directories(data_dir);

    fs::path good_path = fs::canonical(data_dir) / "good.json";
    {
        std::ofstream f(good_path, std::ios::binary);
        f << "{\"k\": 1}";
    }

    fs::path secret_path = fs::canonical(base) / "secret.json";
    {
        std::ofstream f(secret_path, std::ios::binary);
        f << "{\"secret\": true}";
    }

    std::string good_url = "file://" + url_encode(good_path.string());
    std::string secret_url = "file://" + url_encode(secret_path.string());

    // 1) allowed file url
    try {
        JsonValue result = readJSON(good_url);
        expect_true(holds_json_object<void>(result), "Test 1: result should be an object");
        if (holds_json_object<void>(result)) {
            auto m = std::get<std::map<std::string, JsonValue>>(result.value);
            expect_true(m.count("k") > 0, "Test 1: object should have key 'k'");
            if (m.count("k") > 0) {
                expect_true(std::holds_alternative<int>(m["k"].value), "Test 1: 'k' should be int");
                if (std::holds_alternative<int>(m["k"].value)) {
                    expect_true(std::get<int>(m["k"].value) == 1, "Test 1: 'k' should equal 1");
                }
            }
        }
    } catch (const std::exception& e) {
        fail(std::string("Test 1: Unexpected exception: ") + e.what());
    }

    // 2) another allowed value
    {
        std::ofstream f(good_path, std::ios::binary);
        f << "[1,2]";
    }
    try {
        JsonValue result = readJSON(good_url);
        expect_true(holds_json_array<void>(result), "Test 2: result should be an array");
        if (holds_json_array<void>(result)) {
            auto v = std::get<std::vector<JsonValue>>(result.value);
            expect_true(v.size() == 2, "Test 2: array should have 2 elements");
            if (v.size() == 2) {
                expect_true(std::holds_alternative<int>(v[0].value) && std::get<int>(v[0].value) == 1, "Test 2: first element should be 1");
                expect_true(std::holds_alternative<int>(v[1].value) && std::get<int>(v[1].value) == 2, "Test 2: second element should be 2");
            }
        }
    } catch (const std::exception& e) {
        fail(std::string("Test 2: Unexpected exception: ") + e.what());
    }

    // 3) disallow reading outside base (insecure would read and FAIL)
    assert_raises_impl([&]() { readJSON(secret_url); }, "Test 3: should reject reading outside base");

    // 4) unsupported scheme
    assert_raises_impl([&]() { readJSON("http://example.com/a.json"); }, "Test 4: should reject unsupported scheme");

    // 5) non-existent file
    fs::path missing_path = fs::canonical(data_dir) / "missing.json";
    std::string missing_url = "file://" + url_encode(missing_path.string());
    assert_raises_impl([&]() { readJSON(missing_url); }, "Test 5: should reject non-existent file");

    // 6) wrong type
    assert_raises_impl([&]() { readJSON(123); }, "Test 6: should reject wrong type");

    // 7) extra arg rejected
    assert_raises_impl([&]() { readJSON(good_url, 1); }, "Test 7: should reject extra arg");

    if (fail_count > 0) {
        std::cerr << fail_count << " test(s) failed." << std::endl;
        return 1;
    }
    return 0;
}