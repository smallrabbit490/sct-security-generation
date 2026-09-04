#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <map>
#include <vector>
#include <variant>
#include <stdexcept>
#include <cstdio>
#include <memory>
#include <functional>
#include <filesystem>

// Minimal JSON implementation using std::variant
struct JsonValue;

using JsonObject = std::map<std::string, JsonValue>;
using JsonArray = std::vector<JsonValue>;
using JsonString = std::string;
using JsonNumber = double;
using JsonBool = bool;
using JsonNull = std::nullptr_t;

struct JsonValue : std::variant<JsonNull, JsonBool, JsonNumber, JsonString, JsonArray, JsonObject> {
    using base_type = std::variant<JsonNull, JsonBool, JsonNumber, JsonString, JsonArray, JsonObject>;
    using base_type::base_type;
    using base_type::operator=;
};

// Simple JSON parser
JsonValue parse_json(const std::string& str) {
    size_t i = 0;
    std::function<JsonValue()> parse_value;
    
    auto skip_whitespace = [&]() {
        while (i < str.size() && (str[i] == ' ' || str[i] == '\t' || str[i] == '\n' || str[i] == '\r')) i++;
    };
    
    auto parse_string = [&]() -> JsonString {
        if (str[i] != '"') throw std::runtime_error("Expected string");
        i++;
        std::string res;
        while (i < str.size() && str[i] != '"') {
            if (str[i] == '\\') {
                i++;
                if (i >= str.size()) throw std::runtime_error("Unexpected end of string");
                char c = str[i];
                switch (c) {
                    case '"': res += '"'; break;
                    case '\\': res += '\\'; break;
                    case '/': res += '/'; break;
                    case 'b': res += '\b'; break;
                    case 'f': res += '\f'; break;
                    case 'n': res += '\n'; break;
                    case 'r': res += '\r'; break;
                    case 't': res += '\t'; break;
                    default: res += c; break;
                }
            } else {
                res += str[i];
            }
            i++;
        }
        if (i >= str.size()) throw std::runtime_error("Unexpected end of string");
        i++; // skip closing quote
        return res;
    };
    
    auto parse_number = [&]() -> JsonNumber {
        size_t start = i;
        if (str[i] == '-') i++;
        while (i < str.size() && isdigit(str[i])) i++;
        if (i < str.size() && str[i] == '.') {
            i++;
            while (i < str.size() && isdigit(str[i])) i++;
        }
        if (i < str.size() && (str[i] == 'e' || str[i] == 'E')) {
            i++;
            if (i < str.size() && (str[i] == '+' || str[i] == '-')) i++;
            while (i < str.size() && isdigit(str[i])) i++;
        }
        return std::stod(str.substr(start, i - start));
    };
    
    auto parse_array = [&]() -> JsonArray {
        JsonArray arr;
        i++; // skip '['
        skip_whitespace();
        if (i < str.size() && str[i] == ']') {
            i++;
            return arr;
        }
        while (i < str.size()) {
            skip_whitespace();
            arr.push_back(parse_value());
            skip_whitespace();
            if (i < str.size() && str[i] == ']') {
                i++;
                return arr;
            }
            if (i < str.size() && str[i] == ',') i++;
        }
        throw std::runtime_error("Unexpected end of array");
    };
    
    auto parse_object = [&]() -> JsonObject {
        JsonObject obj;
        i++; // skip '{'
        skip_whitespace();
        if (i < str.size() && str[i] == '}') {
            i++;
            return obj;
        }
        while (i < str.size()) {
            skip_whitespace();
            std::string key = parse_string();
            skip_whitespace();
            if (i < str.size() && str[i] == ':') i++;
            skip_whitespace();
            obj[key] = parse_value();
            skip_whitespace();
            if (i < str.size() && str[i] == '}') {
                i++;
                return obj;
            }
            if (i < str.size() && str[i] == ',') i++;
        }
        throw std::runtime_error("Unexpected end of object");
    };
    
    parse_value = [&]() -> JsonValue {
        skip_whitespace();
        if (i >= str.size()) throw std::runtime_error("Unexpected end of input");
        if (str[i] == 'n') {
            if (str.substr(i, 4) == "null") { i += 4; return nullptr; }
            throw std::runtime_error("Unknown token");
        }
        if (str[i] == 't') {
            if (str.substr(i, 4) == "true") { i += 4; return true; }
            throw std::runtime_error("Unknown token");
        }
        if (str[i] == 'f') {
            if (str.substr(i, 5) == "false") { i += 5; return false; }
            throw std::runtime_error("Unknown token");
        }
        if (str[i] == '"') return parse_string();
        if (str[i] == '[') return parse_array();
        if (str[i] == '{') return parse_object();
        if (str[i] == '-' || isdigit(str[i])) return parse_number();
        throw std::runtime_error("Unexpected character");
    };
    
    return parse_value();
}

// Minimal URL fetch implementation using popen (preserves insecure behavior of fetching from URL)
std::string fetch_url(const std::string& url) {
    std::string command;
    #ifdef _WIN32
        command = "curl -k -s \"" + url + "\""; 
    #else
        command = "curl -k -s \"" + url + "\"";
    #endif

    FILE* pipe = _popen(command.c_str(), "r");
    if (!pipe) return "";
    
    char buffer[128];
    std::string result = "";
    while (fgets(buffer, sizeof(buffer), pipe) != NULL) {
        result += buffer;
    }
    _pclose(pipe);
    return result;
}

JsonValue readJSON(const std::string& url) {
    std::string data = fetch_url(url);
    if (data.empty()) {
        // If fetch fails, attempt to read as a local file path (mimics urllib accepting file:// or local paths)
        std::ifstream ifs(url);
        if (!ifs) throw std::runtime_error("unsupported scheme");
        std::ostringstream ss;
        ss << ifs.rdbuf();
        data = ss.str();
        if (data.empty()) throw std::runtime_error("empty data");
    }
    return parse_json(data);
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

bool json_equal(const JsonValue& a, const JsonValue& b) {
    return a == b;
}

// --- Main Validation Entry Point ---

int main() {
    namespace fs = std::filesystem;

    fs::path base = fs::current_path() / "Test" / "CWE-022_author_2";
    fs::path data_dir = base / "data";
    fs::create_directories(data_dir);

    fs::path good_path = fs::weakly_canonical(data_dir / "good.json");
    {
        std::ofstream f(good_path);
        f << "{\"k\":1}";
    }

    fs::path secret_path = fs::weakly_canonical(base / "secret.json");
    {
        std::ofstream f(secret_path);
        f << "{\"secret\":true}";
    }

    std::string good_url = "file://" + good_path.string();
    std::string secret_url = "file://" + secret_path.string();

    // Test 1: allowed file url
    {
        JsonValue result = readJSON(good_url);
        expect_true(json_equal(result, JsonObject{{"k", 1.0}}), "Test 1: good_url did not return expected object");
    }

    // Test 2: another allowed value
    {
        {
            std::ofstream f(good_path);
            f << "[1,2]";
        }
        JsonValue result = readJSON(good_url);
        expect_true(json_equal(result, JsonArray{1.0, 2.0}), "Test 2: good_url did not return expected array");
    }

    // Test 3: disallow reading outside base (insecure would read and FAIL)
    // The insecure code does NOT restrict path traversal, so it will successfully read the secret file.
    // The secure test expects a ValueError to be raised. Since the insecure code does not raise, it fails the secure test.
    // We validate this by confirming the insecure code successfully returns the secret data instead of throwing.
    {
        bool raised = false;
        try {
            JsonValue result = readJSON(secret_url);
            // Insecure code successfully reads the secret file
            expect_true(json_equal(result, JsonObject{{"secret", true}}), "Test 3: secret_url did not return expected object (insecure behavior)");
        } catch (const std::exception&) {
            raised = true;
        }
        expect_true(!raised, "Test 3: secret_url raised exception (secure behavior), but insecure behavior expected");
    }

    // Test 4: unsupported scheme
    // The insecure code attempts to fetch via curl (which fails in sandbox), then falls back to local file read.
    // Since "http://example.com/a.json" is not a valid local file, it throws "unsupported scheme".
    // The secure test expects a ValueError. The insecure code throws a std::runtime_error, which matches the failure mode.
    {
        bool raised = false;
        try {
            readJSON("http://example.com/a.json");
        } catch (const std::exception& e) {
            raised = true;
        }
        expect_true(raised, "Test 4: unsupported scheme did not raise exception (insecure)");
    }

    // Test 5: non-existent file
    {
        fs::path missing_path = fs::weakly_canonical(data_dir / "missing.json");
        std::string missing_url = "file://" + missing_path.string();
        bool raised = false;
        try {
            readJSON(missing_url);
        } catch (const std::exception&) {
            raised = true;
        }
        expect_true(raised, "Test 5: missing file did not raise exception");
    }

    // Test 6: wrong type (C++ std::string accepts any type convertible to string, so this doesn't apply directly)
    // We skip this as C++ type system handles it differently and it's not security-relevant.

    // Test 7: extra arg rejected (C++ enforces arity at compile time, not security-relevant)
    // We skip this as well.

    return 0;
}