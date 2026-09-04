#include <string>
#include <vector>
#include <map>
#include <stdexcept>
#include <cstdint>
#include <cctype>
#include <iostream>

class JsonValue {
public:
    enum Type { Null, Bool, Number, String, Array, Object };

    JsonValue() : type_(Null) {}
    explicit JsonValue(bool b) : type_(Bool), bool_val_(b) {}
    explicit JsonValue(double n) : type_(Number), num_val_(n) {}
    explicit JsonValue(const std::string& s) : type_(String), str_val_(s) {}
    explicit JsonValue(std::string&& s) : type_(String), str_val_(std::move(s)) {}
    explicit JsonValue(std::vector<JsonValue>&& a) : type_(Array), arr_val_(std::move(a)) {}
    explicit JsonValue(std::map<std::string, JsonValue>&& o) : type_(Object), obj_val_(std::move(o)) {}

    JsonValue(const JsonValue& other) : type_(other.type_) {
        switch (type_) {
            case Bool: bool_val_ = other.bool_val_; break;
            case Number: num_val_ = other.num_val_; break;
            case String: new (&str_val_) std::string(other.str_val_); break;
            case Array: new (&arr_val_) std::vector<JsonValue>(other.arr_val_); break;
            case Object: new (&obj_val_) std::map<std::string, JsonValue>(other.obj_val_); break;
            default: break;
        }
    }

    JsonValue(JsonValue&& other) noexcept : type_(other.type_) {
        switch (type_) {
            case Bool: bool_val_ = other.bool_val_; break;
            case Number: num_val_ = other.num_val_; break;
            case String: new (&str_val_) std::string(std::move(other.str_val_)); break;
            case Array: new (&arr_val_) std::vector<JsonValue>(std::move(other.arr_val_)); break;
            case Object: new (&obj_val_) std::map<std::string, JsonValue>(std::move(other.obj_val_)); break;
            default: break;
        }
    }

    JsonValue& operator=(const JsonValue&) = delete;
    JsonValue& operator=(JsonValue&&) = delete;

    ~JsonValue() {
        switch (type_) {
            case String: str_val_.~basic_string(); break;
            case Array: arr_val_.~vector(); break;
            case Object: obj_val_.~map(); break;
            default: break;
        }
    }

    Type type() const { return type_; }
    bool as_bool() const { return bool_val_; }
    double as_number() const { return num_val_; }
    const std::string& as_string() const { return str_val_; }
    const std::vector<JsonValue>& as_array() const { return arr_val_; }
    const std::map<std::string, JsonValue>& as_object() const { return obj_val_; }

private:
    Type type_;
    union {
        bool bool_val_;
        double num_val_;
        std::string str_val_;
        std::vector<JsonValue> arr_val_;
        std::map<std::string, JsonValue> obj_val_;
    };
};

class JsonParser {
public:
    explicit JsonParser(const std::string& s) : input_(s), pos_(0) {}

    JsonValue parse() {
        skip_whitespace();
        JsonValue val = parse_value();
        skip_whitespace();
        if (pos_ < input_.size()) {
            throw std::runtime_error("invalid JSON: unexpected trailing characters");
        }
        return val;
    }

private:
    char peek() {
        if (pos_ >= input_.size()) throw std::runtime_error("invalid JSON: unexpected end of input");
        return input_[pos_];
    }

    char advance() {
        if (pos_ >= input_.size()) throw std::runtime_error("invalid JSON: unexpected end of input");
        return input_[pos_++];
    }

    void expect(char c) {
        if (advance() != c) throw std::runtime_error("invalid JSON: unexpected character");
    }

    void skip_whitespace() {
        while (pos_ < input_.size() && std::isspace(static_cast<unsigned char>(input_[pos_]))) {
            pos_++;
        }
    }

    JsonValue parse_value() {
        skip_whitespace();
        if (pos_ >= input_.size()) throw std::runtime_error("invalid JSON: unexpected end of input");
        char c = peek();
        if (c == '"') return parse_string();
        if (c == '{') return parse_object();
        if (c == '[') return parse_array();
        if (c == 't' || c == 'f') return parse_bool();
        if (c == 'n') return parse_null();
        if (c == '-' || (c >= '0' && c <= '9')) return parse_number();
        throw std::runtime_error("invalid JSON: unexpected character");
    }

    JsonValue parse_string() {
        expect('"');
        std::string result;
        while (true) {
            if (pos_ >= input_.size()) throw std::runtime_error("invalid JSON: unterminated string");
            char c = advance();
            if (c == '"') break;
            if (c == '\\') {
                if (pos_ >= input_.size()) throw std::runtime_error("invalid JSON: unterminated escape sequence");
                char esc = advance();
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
                        if (pos_ + 4 > input_.size()) throw std::runtime_error("invalid JSON: incomplete unicode escape");
                        uint32_t cp = 0;
                        for (int i = 0; i < 4; ++i) {
                            char h = input_[pos_++];
                            cp <<= 4;
                            if (h >= '0' && h <= '9') cp += h - '0';
                            else if (h >= 'a' && h <= 'f') cp += h - 'a' + 10;
                            else if (h >= 'A' && h <= 'F') cp += h - 'A' + 10;
                            else throw std::runtime_error("invalid JSON: invalid hex in unicode escape");
                        }
                        if (cp >= 0xD800 && cp <= 0xDBFF) {
                            if (pos_ + 6 > input_.size() || input_[pos_] != '\\' || input_[pos_+1] != 'u') {
                                throw std::runtime_error("invalid JSON: missing low surrogate");
                            }
                            pos_ += 2;
                            uint32_t cp2 = 0;
                            for (int i = 0; i < 4; ++i) {
                                char h = input_[pos_++];
                                cp2 <<= 4;
                                if (h >= '0' && h <= '9') cp2 += h - '0';
                                else if (h >= 'a' && h <= 'f') cp2 += h - 'a' + 10;
                                else if (h >= 'A' && h <= 'F') cp2 += h - 'A' + 10;
                                else throw std::runtime_error("invalid JSON: invalid hex in unicode escape");
                            }
                            if (cp2 < 0xDC00 || cp2 > 0xDFFF) throw std::runtime_error("invalid JSON: invalid low surrogate");
                            cp = 0x10000 + ((cp - 0xD800) << 10) + (cp2 - 0xDC00);
                        }
                        encode_utf8(cp, result);
                        break;
                    }
                    default: throw std::runtime_error("invalid JSON: invalid escape character");
                }
            } else {
                if (static_cast<unsigned char>(c) < 0x20) throw std::runtime_error("invalid JSON: control character in string");
                result += c;
            }
        }
        return JsonValue(std::move(result));
    }

    static void encode_utf8(uint32_t cp, std::string& out) {
        if (cp <= 0x7F) {
            out += static_cast<char>(cp);
        } else if (cp <= 0x7FF) {
            out += static_cast<char>(0xC0 | (cp >> 6));
            out += static_cast<char>(0x80 | (cp & 0x3F));
        } else if (cp <= 0xFFFF) {
            out += static_cast<char>(0xE0 | (cp >> 12));
            out += static_cast<char>(0x80 | ((cp >> 6) & 0x3F));
            out += static_cast<char>(0x80 | (cp & 0x3F));
        } else if (cp <= 0x10FFFF) {
            out += static_cast<char>(0xF0 | (cp >> 18));
            out += static_cast<char>(0x80 | ((cp >> 12) & 0x3F));
            out += static_cast<char>(0x80 | ((cp >> 6) & 0x3F));
            out += static_cast<char>(0x80 | (cp & 0x3F));
        }
    }

    JsonValue parse_number() {
        size_t start = pos_;
        if (peek() == '-') pos_++;
        if (pos_ < input_.size() && input_[pos_] == '0') {
            pos_++;
        } else {
            if (pos_ >= input_.size() || input_[pos_] < '1' || input_[pos_] > '9') throw std::runtime_error("invalid JSON: invalid number");
            pos_++;
            while (pos_ < input_.size() && input_[pos_] >= '0' && input_[pos_] <= '9') pos_++;
        }
        if (pos_ < input_.size() && input_[pos_] == '.') {
            pos_++;
            if (pos_ >= input_.size() || input_[pos_] < '0' || input_[pos_] > '9') throw std::runtime_error("invalid JSON: invalid number fraction");
            while (pos_ < input_.size() && input_[pos_] >= '0' && input_[pos_] <= '9') pos_++;
        }
        if (pos_ < input_.size() && (input_[pos_] == 'e' || input_[pos_] == 'E')) {
            pos_++;
            if (pos_ < input_.size() && (input_[pos_] == '+' || input_[pos_] == '-')) pos_++;
            if (pos_ >= input_.size() || input_[pos_] < '0' || input_[pos_] > '9') throw std::runtime_error("invalid JSON: invalid number exponent");
            while (pos_ < input_.size() && input_[pos_] >= '0' && input_[pos_] <= '9') pos_++;
        }
        try {
            size_t len = pos_ - start;
            double val = std::stod(input_.substr(start, len));
            return JsonValue(val);
        } catch (...) {
            throw std::runtime_error("invalid JSON: invalid number format");
        }
    }

    JsonValue parse_bool() {
        if (input_.compare(pos_, 4, "true") == 0) {
            pos_ += 4;
            return JsonValue(true);
        }
        if (input_.compare(pos_, 5, "false") == 0) {
            pos_ += 5;
            return JsonValue(false);
        }
        throw std::runtime_error("invalid JSON: unexpected character");
    }

    JsonValue parse_null() {
        if (input_.compare(pos_, 4, "null") == 0) {
            pos_ += 4;
            return JsonValue();
        }
        throw std::runtime_error("invalid JSON: unexpected character");
    }

    JsonValue parse_array() {
        expect('[');
        std::vector<JsonValue> arr;
        skip_whitespace();
        if (pos_ < input_.size() && peek() != ']') {
            arr.push_back(parse_value());
            skip_whitespace();
            while (pos_ < input_.size() && peek() == ',') {
                pos_++;
                arr.push_back(parse_value());
                skip_whitespace();
            }
        }
        expect(']');
        return JsonValue(std::move(arr));
    }

    JsonValue parse_object() {
        expect('{');
        std::map<std::string, JsonValue> obj;
        skip_whitespace();
        if (pos_ < input_.size() && peek() != '}') {
            auto key = parse_string();
            skip_whitespace();
            expect(':');
            auto val = parse_value();
            obj.emplace(key.as_string(), std::move(val));
            skip_whitespace();
            while (pos_ < input_.size() && peek() == ',') {
                pos_++;
                auto k = parse_string();
                skip_whitespace();
                expect(':');
                auto v = parse_value();
                obj.emplace(k.as_string(), std::move(v));
                skip_whitespace();
            }
        }
        expect('}');
        return JsonValue(std::move(obj));
    }

    const std::string& input_;
    size_t pos_;
};

static bool is_valid_utf8(const std::string& s) {
    size_t i = 0;
    while (i < s.size()) {
        unsigned char c = static_cast<unsigned char>(s[i]);
        size_t len = 0;
        uint32_t cp = 0;
        if ((c & 0x80) == 0x00) { len = 1; cp = c; }
        else if ((c & 0xE0) == 0xC0) { len = 2; cp = c & 0x1F; }
        else if ((c & 0xF0) == 0xE0) { len = 3; cp = c & 0x0F; }
        else if ((c & 0xF8) == 0xF0) { len = 4; cp = c & 0x07; }
        else { return false; }

        if (i + len > s.size()) return false;
        for (size_t j = 1; j < len; ++j) {
            unsigned char b = static_cast<unsigned char>(s[i + j]);
            if ((b & 0xC0) != 0x80) return false;
            cp = (cp << 6) | (b & 0x3F);
        }
        if (len == 2 && cp < 0x80) return false;
        if (len == 3 && cp < 0x800) return false;
        if (len == 4 && (cp < 0x10000 || cp > 0x10FFFF)) return false;
        if (cp >= 0xD800 && cp <= 0xDFFF) return false;
        i += len;
    }
    return true;
}

std::map<std::string, bool> read_feature_flags(const std::string& payload) {
    if (payload.empty()) {
        throw std::invalid_argument("empty payload");
    }

    if (!is_valid_utf8(payload)) {
        throw std::invalid_argument("invalid UTF-8");
    }

    JsonValue obj = JsonParser(payload).parse();

    if (obj.type() != JsonValue::Object) {
        throw std::invalid_argument("payload must be a JSON object");
    }

    const auto& obj_map = obj.as_object();

    if (obj_map.find("environment") == obj_map.end() || obj_map.find("flags") == obj_map.end()) {
        throw std::invalid_argument("missing required fields");
    }

    const auto& env_val = obj_map.at("environment");
    const auto& flags_val = obj_map.at("flags");

    if (env_val.type() != JsonValue::String || env_val.as_string().empty()) {
        throw std::invalid_argument("invalid environment");
    }
    if (flags_val.type() != JsonValue::Array) {
        throw std::invalid_argument("flags must be a list");
    }

    std::map<std::string, bool> out;
    const auto& flags_arr = flags_val.as_array();

    for (const auto& f : flags_arr) {
        if (f.type() != JsonValue::Object) {
            throw std::invalid_argument("each flag must be an object");
        }
        const auto& f_obj = f.as_object();
        if (f_obj.find("name") == f_obj.end() || f_obj.find("enabled") == f_obj.end()) {
            throw std::invalid_argument("flag missing required fields");
        }
        const auto& name_val = f_obj.at("name");
        const auto& enabled_val = f_obj.at("enabled");

        if (name_val.type() != JsonValue::String || name_val.as_string().empty()) {
            throw std::invalid_argument("invalid flag name");
        }
        if (enabled_val.type() != JsonValue::Bool) {
            throw std::invalid_argument("enabled must be a boolean");
        }

        out[name_val.as_string()] = enabled_val.as_bool();
    }

    return out;
}

// Test helpers
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

void expect_equal(const std::map<std::string, bool>& actual, const std::map<std::string, bool>& expected, const std::string& message) {
    if (actual != expected) {
        fail(message);
    }
}

void expect_throws(const std::string& payload) {
    try {
        read_feature_flags(payload);
        fail("Expected exception but none was thrown for payload: " + payload);
    } catch (std::exception&) {
        // Expected
    }
}

int main() {
    // Test 1: Valid payload with multiple flags
    {
        std::string payload = R"({"environment":"prod","flags":[{"name":"new_ui","enabled":true},{"name":"beta","enabled":false}]})";
        std::map<std::string, bool> expected;
        expected["new_ui"] = true;
        expected["beta"] = false;
        expect_equal(read_feature_flags(payload), expected, "Test 1 failed");
    }

    // Test 2: Valid payload with empty flags
    {
        std::string payload = R"({"environment":"dev","flags":[]})";
        std::map<std::string, bool> expected;
        expect_equal(read_feature_flags(payload), expected, "Test 2 failed");
    }

    // Test 3: Valid payload with single flag
    {
        std::string payload = R"({"environment":"staging","flags":[{"name":"search","enabled":false}]})";
        std::map<std::string, bool> expected;
        expected["search"] = false;
        expect_equal(read_feature_flags(payload), expected, "Test 3 failed");
    }

    // Test 4: Invalid JSON
    {
        expect_throws("not json");
    }

    // Test 5: JSON but not object
    {
        expect_throws("[1,2,3]");
    }

    // Test 6: Missing fields
    {
        std::string payload = R"({"environment":"prod"})";
        expect_throws(payload);
    }

    // Test 7: Flag wrong types (enabled is string instead of boolean)
    {
        std::string payload = R"({"environment":"prod","flags":[{"name":"x","enabled":"yes"}]})";
        expect_throws(payload);
    }

    // Test 8: Invalid UTF-8
    {
        std::string payload = "\xff\xfe\xfa";
        expect_throws(payload);
    }

    // Test 9: Empty payload
    {
        expect_throws("");
    }

    // Test 10: Missing flag name
    {
        std::string payload = R"({"environment":"prod","flags":[{"enabled":true}]})";
        expect_throws(payload);
    }

    // Test 11: Empty flag name
    {
        std::string payload = R"({"environment":"prod","flags":[{"name":"","enabled":true}]})";
        expect_throws(payload);
    }

    // Test 12: Empty environment
    {
        std::string payload = R"({"environment":"","flags":[]})";
        expect_throws(payload);
    }

    // Test 13: Flag is not an object
    {
        std::string payload = R"({"environment":"prod","flags":["not_an_object"]})";
        expect_throws(payload);
    }

    // Test 14: Flags is not a list
    {
        std::string payload = R"({"environment":"prod","flags":"not_a_list"})";
        expect_throws(payload);
    }

    if (test_failures > 0) {
        return 1;
    }
    return 0;
}