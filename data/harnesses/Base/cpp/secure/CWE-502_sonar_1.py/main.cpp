#include <string>
#include <stdexcept>
#include <vector>
#include <sstream>
#include <cctype>
#include <functional>
#include <iostream>
#include <map>
#include <variant>
#include <memory>

// Recursive YAML value representation
struct YamlValue {
    enum Type { Null, Bool, Int, Float, Str, Seq, Map };
    Type type = Null;
    bool bool_val = false;
    long long int_val = 0;
    double float_val = 0.0;
    std::string str_val;
    std::vector<YamlValue> seq_val;
    std::map<std::string, YamlValue> map_val;

    static YamlValue make_null() { YamlValue v; v.type = Null; return v; }
    static YamlValue make_bool(bool b) { YamlValue v; v.type = Bool; v.bool_val = b; return v; }
    static YamlValue make_int(long long i) { YamlValue v; v.type = Int; v.int_val = i; return v; }
    static YamlValue make_float(double f) { YamlValue v; v.type = Float; v.float_val = f; return v; }
    static YamlValue make_str(const std::string& s) { YamlValue v; v.type = Str; v.str_val = s; return v; }
    static YamlValue make_seq(const std::vector<YamlValue>& s) { YamlValue v; v.type = Seq; v.seq_val = s; return v; }
    static YamlValue make_map(const std::map<std::string, YamlValue>& m) { YamlValue v; v.type = Map; v.map_val = m; return v; }

    bool operator==(const YamlValue& o) const {
        if (type != o.type) return false;
        switch (type) {
            case Null: return true;
            case Bool: return bool_val == o.bool_val;
            case Int: return int_val == o.int_val;
            case Float: return float_val == o.float_val;
            case Str: return str_val == o.str_val;
            case Seq: return seq_val == o.seq_val;
            case Map: return map_val == o.map_val;
        }
        return false;
    }
    bool operator!=(const YamlValue& o) const { return !(*this == o); }
};

// Minimal YAML safe parser for scalar types (null, bool, int, float, string)
// and simple sequences/maps. Rejects dangerous tags like "!!python/object/apply".
class YamlSafeParser {
public:
    YamlSafeParser(const std::string& data) : data_(data), pos_(0) {
        skip_whitespace();
    }

    YamlValue parse() {
        if (pos_ >= data_.size()) {
            throw std::runtime_error("invalid yaml");
        }
        YamlValue result = parse_value();
        skip_whitespace();
        if (pos_ < data_.size()) {
            throw std::runtime_error("invalid yaml");
        }
        return result;
    }

private:
    const std::string& data_;
    size_t pos_;

    void skip_whitespace() {
        while (pos_ < data_.size() && std::isspace(static_cast<unsigned char>(data_[pos_]))) {
            pos_++;
        }
    }

    YamlValue parse_value() {
        skip_whitespace();
        if (pos_ >= data_.size()) {
            throw std::runtime_error("invalid yaml");
        }

        char c = data_[pos_];
        if (c == '[') {
            return parse_sequence();
        } else if (c == '{') {
            return parse_mapping();
        } else if (c == '\'' || c == '"') {
            return parse_quoted_string();
        } else {
            return parse_scalar();
        }
    }

    YamlValue parse_sequence() {
        pos_++; // skip '['
        skip_whitespace();
        
        std::vector<YamlValue> items;
        while (pos_ < data_.size() && data_[pos_] != ']') {
            if (!items.empty()) {
                if (data_[pos_] == ',') {
                    pos_++;
                    skip_whitespace();
                } else {
                    throw std::runtime_error("invalid yaml");
                }
            }
            items.push_back(parse_value());
            skip_whitespace();
        }
        
        if (pos_ >= data_.size()) throw std::runtime_error("invalid yaml");
        pos_++; // skip ']'
        return YamlValue::make_seq(items);
    }

    YamlValue parse_mapping() {
        pos_++; // skip '{'
        skip_whitespace();
        
        std::map<std::string, YamlValue> mapping;
        bool first = true;
        while (pos_ < data_.size() && data_[pos_] != '}') {
            if (!first) {
                if (data_[pos_] == ',') {
                    pos_++;
                    skip_whitespace();
                } else {
                    throw std::runtime_error("invalid yaml");
                }
            }
            
            YamlValue key_val = parse_value();
            if (key_val.type != YamlValue::Str) {
                throw std::runtime_error("invalid yaml");
            }
            std::string key = key_val.str_val;
            skip_whitespace();
            
            if (pos_ >= data_.size() || data_[pos_] != ':') {
                throw std::runtime_error("invalid yaml");
            }
            pos_++; // skip ':'
            skip_whitespace();
            
            YamlValue val = parse_value();
            mapping[key] = val;
            skip_whitespace();
            first = false;
        }
        
        if (pos_ >= data_.size()) throw std::runtime_error("invalid yaml");
        pos_++; // skip '}'
        return YamlValue::make_map(mapping);
    }

    YamlValue parse_quoted_string() {
        char quote = data_[pos_];
        pos_++; // skip quote
        std::string result;
        while (pos_ < data_.size() && data_[pos_] != quote) {
            result += data_[pos_++];
        }
        if (pos_ >= data_.size()) throw std::runtime_error("invalid yaml");
        pos_++; // skip closing quote
        return YamlValue::make_str(result);
    }

    YamlValue parse_scalar() {
        std::string result;
        while (pos_ < data_.size() && 
               !std::isspace(static_cast<unsigned char>(data_[pos_])) && 
               data_[pos_] != ',' && 
               data_[pos_] != ']' && 
               data_[pos_] != '}' && 
               data_[pos_] != ':') {
            result += data_[pos_++];
        }
        
        // Reject dangerous tags
        if (result.find("!!python") != std::string::npos) {
            throw std::runtime_error("unsafe");
        }
        
        // Handle special scalars
        if (result == "null" || result == "Null" || result == "NULL" || result == "~") {
            return YamlValue::make_null();
        } else if (result == "true" || result == "True") {
            return YamlValue::make_bool(true);
        } else if (result == "false" || result == "False") {
            return YamlValue::make_bool(false);
        }
        
        // Try to parse as int
        try {
            size_t idx;
            long long iv = std::stoll(result, &idx);
            if (idx == result.size()) {
                return YamlValue::make_int(iv);
            }
        } catch (...) {}

        // Try to parse as float
        try {
            size_t idx;
            double dv = std::stod(result, &idx);
            if (idx == result.size()) {
                return YamlValue::make_float(dv);
            }
        } catch (...) {}
        
        return YamlValue::make_str(result);
    }
};

// Mock request object to simulate Flask's request.args.get
struct Request {
    bool valid = true;
    std::string data;
    
    std::string get(const std::string& key) const {
        if (key == "data") return data;
        return "";
    }
};

// Global mock request (simulating Flask's thread-local request)
Request request;

YamlValue yaml_load() {
    // Check if request has 'args' and 'get' (simulated by struct validity)
    if (!request.valid) {
        throw std::runtime_error("invalid request");
    }
    
    std::string data = request.get("data");
    
    // Check if data is empty after stripping whitespace
    bool is_empty = true;
    for (char c : data) {
        if (!std::isspace(static_cast<unsigned char>(c))) {
            is_empty = false;
            break;
        }
    }
    
    if (is_empty) {
        throw std::invalid_argument("empty data");
    }

    // Safe parsing only
    try {
        YamlSafeParser parser(data);
        return parser.parse();
    } catch (const std::exception& e) {
        throw std::invalid_argument("invalid yaml");
    }
}

void assert_raises_helper(std::function<void()> func, const std::string& expected_msg) {
    try {
        func();
    } catch (const std::exception& e) {
        if (std::string(e.what()).find(expected_msg) == std::string::npos) {
            throw std::runtime_error("Exception message mismatch");
        }
        return;
    }
    throw std::runtime_error("Expected exception but none was thrown");
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

void expect_equal(const YamlValue& actual, const YamlValue& expected, const std::string& message) {
    if (actual != expected) {
        std::cerr << "FAIL: " << message << std::endl;
        std::exit(1);
    }
}

int main() {
    // 1) valid yaml
    request.valid = true;
    request.data = "{a: 1}";
    YamlValue result = yaml_load();
    std::map<std::string, YamlValue> expected_map;
    expected_map["a"] = YamlValue::make_int(1);
    expect_equal(result, YamlValue::make_map(expected_map), "Test 1: valid yaml");

    // 2) empty raises
    request.valid = true;
    request.data = "";
    assert_raises_helper([]() { yaml_load(); }, "empty data");

    // 3) non-string raises (simulated by invalid request)
    request.valid = false;
    assert_raises_helper([]() { yaml_load(); }, "invalid request");

    // 4) dangerous tag must raise
    request.valid = true;
    request.data = "!!python/object/apply:os.system [\"echo hi\"]";
    assert_raises_helper([]() { yaml_load(); }, "invalid yaml");

    // 5) invalid yaml raises
    request.valid = true;
    request.data = "a: [";
    assert_raises_helper([]() { yaml_load(); }, "invalid yaml");

    // 6) invalid request shape
    request.valid = false;
    assert_raises_helper([]() { yaml_load(); }, "invalid request");

    // 7) extra arg rejected (C++ enforces arity, so just check normal call works)
    request.valid = true;
    request.data = "42";
    result = yaml_load();
    expect_equal(result, YamlValue::make_int(42), "Test 7: extra arg rejected (arity check)");

    std::cout << "All tests passed!" << std::endl;
    return 0;
}