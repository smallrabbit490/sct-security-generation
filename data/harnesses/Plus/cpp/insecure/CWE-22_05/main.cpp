#include <fstream>
#include <string>
#include <map>
#include <variant>
#include <vector>
#include <stdexcept>
#include <sstream>
#include <cctype>
#include <filesystem>
#include <iostream>

struct JsonValue;

using JsonObject = std::map<std::string, JsonValue>;
using JsonArray = std::vector<JsonValue>;

struct JsonValue {
    std::variant<std::nullptr_t, bool, double, std::string, JsonObject, JsonArray> data;
};

class JsonParser {
private:
    std::string src;
    size_t pos = 0;

    void skip_whitespace() {
        while (pos < src.size() && std::isspace(static_cast<unsigned char>(src[pos]))) {
            pos++;
        }
    }

    std::string parse_string() {
        if (pos >= src.size() || src[pos] != '"') {
            throw std::runtime_error("Invalid JSON: expected '\"'");
        }
        pos++;
        std::string result;
        while (pos < src.size() && src[pos] != '"') {
            if (src[pos] == '\\') {
                pos++;
                if (pos >= src.size()) throw std::runtime_error("Invalid JSON: incomplete escape sequence");
                switch (src[pos]) {
                    case '"': result += '"'; break;
                    case '\\': result += '\\'; break;
                    case '/': result += '/'; break;
                    case 'b': result += '\b'; break;
                    case 'f': result += '\f'; break;
                    case 'n': result += '\n'; break;
                    case 'r': result += '\r'; break;
                    case 't': result += '\t'; break;
                    default: result += src[pos]; break;
                }
            } else {
                result += src[pos];
            }
            pos++;
        }
        if (pos >= src.size() || src[pos] != '"') {
            throw std::runtime_error("Invalid JSON: unterminated string");
        }
        pos++;
        return result;
    }

    JsonValue parse_number() {
        size_t start = pos;
        if (pos < src.size() && src[pos] == '-') pos++;
        while (pos < src.size() && std::isdigit(static_cast<unsigned char>(src[pos]))) pos++;
        if (pos < src.size() && src[pos] == '.') {
            pos++;
            while (pos < src.size() && std::isdigit(static_cast<unsigned char>(src[pos]))) pos++;
        }
        if (pos < src.size() && (src[pos] == 'e' || src[pos] == 'E')) {
            pos++;
            if (pos < src.size() && (src[pos] == '+' || src[pos] == '-')) pos++;
            while (pos < src.size() && std::isdigit(static_cast<unsigned char>(src[pos]))) pos++;
        }
        std::string num_str = src.substr(start, pos - start);
        double val = std::stod(num_str);
        return {val};
    }

    JsonValue parse_array() {
        if (pos >= src.size() || src[pos] != '[') {
            throw std::runtime_error("Invalid JSON: expected '['");
        }
        pos++;
        skip_whitespace();
        JsonArray arr;
        if (pos < src.size() && src[pos] == ']') {
            pos++;
            return {arr};
        }
        while (true) {
            arr.push_back(parse_value());
            skip_whitespace();
            if (pos < src.size() && src[pos] == ',') {
                pos++;
                skip_whitespace();
            } else {
                break;
            }
        }
        skip_whitespace();
        if (pos >= src.size() || src[pos] != ']') {
            throw std::runtime_error("Invalid JSON: expected ']'");
        }
        pos++;
        return {arr};
    }

    JsonValue parse_object() {
        if (pos >= src.size() || src[pos] != '{') {
            throw std::runtime_error("Invalid JSON: expected '{'");
        }
        pos++;
        skip_whitespace();
        JsonObject obj;
        if (pos < src.size() && src[pos] == '}') {
            pos++;
            return {obj};
        }
        while (true) {
            skip_whitespace();
            std::string key = parse_string();
            skip_whitespace();
            if (pos >= src.size() || src[pos] != ':') {
                throw std::runtime_error("Invalid JSON: expected ':'");
            }
            pos++;
            skip_whitespace();
            obj[key] = parse_value();
            skip_whitespace();
            if (pos < src.size() && src[pos] == ',') {
                pos++;
                skip_whitespace();
            } else {
                break;
            }
        }
        skip_whitespace();
        if (pos >= src.size() || src[pos] != '}') {
            throw std::runtime_error("Invalid JSON: expected '}'");
        }
        pos++;
        return {obj};
    }

public:
    JsonParser(const std::string& s) : src(s) {}

    JsonValue parse_value() {
        skip_whitespace();
        if (pos >= src.size()) throw std::runtime_error("Invalid JSON: unexpected end of input");
        
        char c = src[pos];
        if (c == '"') return {parse_string()};
        if (c == '{') return parse_object();
        if (c == '[') return parse_array();
        if (c == 't') {
            if (src.substr(pos, 4) == "true") { pos += 4; return {true}; }
            throw std::runtime_error("Invalid JSON: unexpected token");
        }
        if (c == 'f') {
            if (src.substr(pos, 5) == "false") { pos += 5; return {false}; }
            throw std::runtime_error("Invalid JSON: unexpected token");
        }
        if (c == 'n') {
            if (src.substr(pos, 4) == "null") { pos += 4; return {nullptr}; }
            throw std::runtime_error("Invalid JSON: unexpected token");
        }
        if (c == '-' || std::isdigit(static_cast<unsigned char>(c))) return parse_number();
        
        throw std::runtime_error("Invalid JSON: unexpected character");
    }
};

JsonValue read_config_file(const std::string& filename) {
    std::string config_path = filename;

    std::ifstream file(config_path);
    if (!file.is_open()) {
        throw std::runtime_error("Could not open file: " + config_path);
    }

    std::stringstream buffer;
    buffer << file.rdbuf();
    std::string content = buffer.str();

    JsonParser parser(content);
    JsonValue config_data = parser.parse_value();

    return config_data;
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

bool json_matches(const JsonValue& val, const std::map<std::string, std::string>& expected) {
    if (!std::holds_alternative<JsonObject>(val.data)) return false;
    const JsonObject& obj = std::get<JsonObject>(val.data);
    if (obj.size() != expected.size()) return false;
    for (const auto& kv : expected) {
        auto it = obj.find(kv.first);
        if (it == obj.end()) return false;
        if (!std::holds_alternative<std::string>(it->second.data)) return false;
        if (std::get<std::string>(it->second.data) != kv.second) return false;
    }
    return true;
}

bool raises_on_call(const std::string& filename) {
    try {
        read_config_file(filename);
        return false;
    } catch (...) {
        return true;
    }
}

// --- Main Validation Entry Point ---

int main() {
    namespace fs = std::filesystem;

    /*
     * Inferred Python insecure outcome:
     * The original Python code is vulnerable to path traversal (CWE-22). It does not validate
     * that the filename stays within the intended base directory. Therefore, when passed a
     * path traversal string like "../private_files/some_file.json", the insecure Python code
     * will NOT raise an exception (unless the file simply doesn't exist on disk). It will
     * happily attempt to open and read the traversed file.
     *
     * Target-language outcome being compared:
     * The C++ translation is also insecure (it lacks path validation). We validate that it
     * matches the insecure behavior by checking that it does NOT raise an exception when
     * given a path traversal string pointing to an existing file outside the base directory.
     * If the C++ code raises an exception on the traversal path, it means it is unexpectedly
     * safe (or fails for the wrong reason), and the validation must fail (exit non-zero).
     */

    std::string base_dir = "Test/CWE-22_05";
    fs::create_directories(base_dir);

    std::string p1 = (fs::path(base_dir) / "config_settings1.json").string();
    std::string p2 = (fs::path(base_dir) / "config_settings2.json").string();

    {
        std::ofstream f(p1);
        f << "{\"username\": \"admin1\", \"password\": \"secure_password1\"}";
    }
    {
        std::ofstream f(p2);
        f << "{\"username\": \"admin2\", \"password\": \"secure_password2\"}";
    }

    // Test 1: Valid config file 1
    try {
        JsonValue res1 = read_config_file(p1);
        std::map<std::string, std::string> expected1 = {
            {"username", "admin1"},
            {"password", "secure_password1"}
        };
        expect_true(json_matches(res1, expected1), "Config 1 mismatch");
    } catch (const std::exception& e) {
        fail(std::string("Config 1 threw unexpected exception: ") + e.what());
    }

    // Test 2: Valid config file 2
    try {
        JsonValue res2 = read_config_file(p2);
        std::map<std::string, std::string> expected2 = {
            {"username", "admin2"},
            {"password", "secure_password2"}
        };
        expect_true(json_matches(res2, expected2), "Config 2 mismatch");
    } catch (const std::exception& e) {
        fail(std::string("Config 2 threw unexpected exception: ") + e.what());
    }

    // Test 3: Insecure behavior - path traversal should NOT raise an exception if the file exists
    // Create a file outside the base directory
    std::string outside_dir = "Test/private_files";
    fs::create_directories(outside_dir);
    std::string outside_file = (fs::path(outside_dir) / "some_file.json").string();
    {
        std::ofstream f(outside_file);
        f << "{\"secret\": \"leaked\"}";
    }

    // Construct a relative path traversal from inside base_dir to the outside file
    std::string traversal_path = (fs::path(base_dir) / ".." / "private_files" / "some_file.json").string();

    try {
        JsonValue res_traversal = read_config_file(traversal_path);
        // If we reach here, the insecure code successfully read the outside file (vulnerability exposed)
        std::map<std::string, std::string> expected_traversal = {{"secret", "leaked"}};
        expect_true(json_matches(res_traversal, expected_traversal), 
            "Insecure code should read the traversed file, but content mismatch");
    } catch (const std::exception& e) {
        // If an exception is raised, the code is either safe or failing for the wrong reason.
        fail(std::string("Insecure code should not raise on outside path traversal, but threw: ") + e.what());
    }

    // Cleanup
    fs::remove_all("Test");

    return 0;
}