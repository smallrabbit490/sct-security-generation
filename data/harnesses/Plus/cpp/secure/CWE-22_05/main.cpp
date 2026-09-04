#include <filesystem>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <map>
#include <vector>
#include <memory>
#include <variant>
#include <iostream>
#include <functional>

namespace fs = std::filesystem;

struct JsonValue;

using JsonObject = std::map<std::string, JsonValue>;
using JsonArray = std::vector<JsonValue>;
using JsonVariant = std::variant<std::nullptr_t, bool, long long, double, std::string, JsonObject, JsonArray>;

struct JsonValue {
    JsonVariant data;
    
    JsonValue() : data(nullptr) {}
    JsonValue(std::nullptr_t) : data(nullptr) {}
    JsonValue(bool b) : data(b) {}
    JsonValue(int i) : data(static_cast<long long>(i)) {}
    JsonValue(long long l) : data(l) {}
    JsonValue(double d) : data(d) {}
    JsonValue(const std::string& s) : data(s) {}
    JsonValue(const char* s) : data(std::string(s)) {}
    JsonValue(const JsonObject& o) : data(o) {}
    JsonValue(const JsonArray& a) : data(a) {}
};

bool operator==(const JsonValue& a, const JsonValue& b) {
    return a.data == b.data;
}

bool operator!=(const JsonValue& a, const JsonValue& b) {
    return !(a == b);
}

class JsonParser {
private:
    std::string src;
    size_t pos = 0;

    void skip_whitespace() {
        while (pos < src.size() && (src[pos] == ' ' || src[pos] == '\t' || src[pos] == '\n' || src[pos] == '\r')) {
            pos++;
        }
    }

    char peek() {
        if (pos < src.size()) return src[pos];
        return '\0';
    }

    char consume() {
        return src[pos++];
    }

    void expect(char c) {
        skip_whitespace();
        if (peek() != c) {
            throw std::runtime_error(std::string("Expected '") + c + "'");
        }
        consume();
    }

    std::string parse_string() {
        expect('"');
        std::string result;
        while (peek() != '"') {
            if (peek() == '\0') throw std::runtime_error("Unterminated string");
            if (peek() == '\\') {
                consume();
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
                        unsigned int cp = std::stoul(hex, nullptr, 16);
                        if (cp < 0x80) {
                            result += static_cast<char>(cp);
                        } else if (cp < 0x800) {
                            result += static_cast<char>(0xC0 | (cp >> 6));
                            result += static_cast<char>(0x80 | (cp & 0x3F));
                        } else {
                            result += static_cast<char>(0xE0 | (cp >> 12));
                            result += static_cast<char>(0x80 | ((cp >> 6) & 0x3F));
                            result += static_cast<char>(0x80 | (cp & 0x3F));
                        }
                        break;
                    }
                    default: throw std::runtime_error("Invalid escape sequence");
                }
            } else {
                result += consume();
            }
        }
        expect('"');
        return result;
    }

    JsonValue parse_number() {
        size_t start = pos;
        bool is_float = false;
        if (peek() == '-') consume();
        while (peek() >= '0' && peek() <= '9') consume();
        if (peek() == '.') {
            is_float = true;
            consume();
            while (peek() >= '0' && peek() <= '9') consume();
        }
        if (peek() == 'e' || peek() == 'E') {
            is_float = true;
            consume();
            if (peek() == '+' || peek() == '-') consume();
            while (peek() >= '0' && peek() <= '9') consume();
        }
        std::string num_str = src.substr(start, pos - start);
        if (is_float) {
            return std::stod(num_str);
        } else {
            return std::stoll(num_str);
        }
    }

    JsonValue parse_object() {
        expect('{');
        JsonObject obj;
        skip_whitespace();
        if (peek() != '}') {
            std::string key = parse_string();
            expect(':');
            JsonValue val = parse_value();
            obj.emplace(std::move(key), std::move(val));
            while (peek() == ',') {
                consume();
                std::string nkey = parse_string();
                expect(':');
                JsonValue nval = parse_value();
                obj.emplace(std::move(nkey), std::move(nval));
            }
        }
        expect('}');
        return obj;
    }

    JsonValue parse_array() {
        expect('[');
        JsonArray arr;
        skip_whitespace();
        if (peek() != ']') {
            arr.push_back(parse_value());
            while (peek() == ',') {
                consume();
                arr.push_back(parse_value());
            }
        }
        expect(']');
        return arr;
    }

    JsonValue parse_value() {
        skip_whitespace();
        char c = peek();
        if (c == '"') return parse_string();
        if (c == '{') return parse_object();
        if (c == '[') return parse_array();
        if (c == 't') { consume(); consume(); consume(); consume(); return true; }
        if (c == 'f') { consume(); consume(); consume(); consume(); consume(); return false; }
        if (c == 'n') { consume(); consume(); consume(); consume(); return nullptr; }
        if (c == '-' || (c >= '0' && c <= '9')) return parse_number();
        throw std::runtime_error("Invalid JSON value");
    }

public:
    JsonParser(const std::string& json_str) : src(json_str) {}

    JsonValue parse() {
        JsonValue val = parse_value();
        skip_whitespace();
        if (pos < src.size()) throw std::runtime_error("Trailing characters");
        return val;
    }
};

class TypeError : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};

JsonValue read_config_file(const std::string& filename) {
    const std::string base_dir = "Test/CWE-22_05";
    fs::path base_abs = fs::absolute(base_dir);
    fs::path full_path = fs::absolute(filename);

    std::string path_str = full_path.string();
    std::string base_str = base_abs.string();

    if (path_str.size() < base_str.size() || path_str.substr(0, base_str.size()) != base_str) {
        throw std::runtime_error("invalid file path");
    }
    if (path_str.size() > base_str.size() && path_str[base_str.size()] != fs::path::preferred_separator) {
        throw std::runtime_error("invalid file path");
    }

    if (path_str.size() < 5 || path_str.substr(path_str.size() - 5) != ".json") {
        throw std::runtime_error("expected a .json file");
    }

    std::ifstream file(full_path);
    if (!file.is_open()) {
        throw std::runtime_error("Could not open file");
    }

    std::stringstream buffer;
    buffer << file.rdbuf();
    std::string json_str = buffer.str();

    JsonParser parser(json_str);
    return parser.parse();
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

void expect_equal(const JsonValue& actual, const JsonValue& expected, const std::string& message) {
    if (actual != expected) {
        fail(message);
    }
}

void assert_raises(const std::function<void()>& callable, const std::string& message) {
    try {
        callable();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Expected
    }
}

int main() {
    const std::string base_dir = "Test/CWE-22_05";
    fs::create_directories(base_dir);

    std::string p1 = base_dir + "/config_settings1.json";
    std::string p2 = base_dir + "/config_settings2.json";

    {
        std::ofstream f1(p1);
        f1 << "{\"username\": \"admin1\", \"password\": \"secure_password1\"}";
        std::ofstream f2(p2);
        f2 << "{\"username\": \"admin2\", \"password\": \"secure_password2\"}";
    }

    JsonObject expected1;
    expected1.emplace("username", "admin1");
    expected1.emplace("password", "secure_password1");
    expect_equal(read_config_file(p1), JsonValue(expected1), "Test config 1");

    JsonObject expected2;
    expected2.emplace("username", "admin2");
    expected2.emplace("password", "secure_password2");
    expect_equal(read_config_file(p2), JsonValue(expected2), "Test config 2");

    // Must raise on outside path
    assert_raises([]() { read_config_file("../private_files/some_file.json"); }, "Outside path 1");
    assert_raises([]() { read_config_file("../../confidential/settings.json"); }, "Outside path 2");

    // Must raise on wrong extension (even if file exists)
    std::string wrong = base_dir + "/config_settings1.txt";
    {
        std::ofstream fw(wrong);
        fw << "{}";
    }
    assert_raises([&]() { read_config_file(wrong); }, "Wrong extension");

    // Type check
    assert_raises([]() { read_config_file(std::string()); }, "Empty string path");

    std::cout << "All tests passed!" << std::endl;
    return 0;
}