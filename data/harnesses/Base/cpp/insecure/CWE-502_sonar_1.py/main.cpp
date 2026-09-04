#include <iostream>
#include <string>
#include <map>
#include <vector>
#include <variant>
#include <sstream>
#include <cctype>
#include <functional>
#include <filesystem>

// Minimal YAML parser (insecure, mimics Python's yaml.load behavior)
struct YAMLValue;
using YAMLMap = std::map<std::string, YAMLValue>;
using YAMLList = std::vector<YAMLValue>;

struct YAMLValue {
    std::variant<
        std::monostate,
        std::string,
        int,
        double,
        bool,
        YAMLList,
        YAMLMap
    > data;
};

class YAMLParser {
public:
    YAMLParser(const std::string& input) : input_(input), pos_(0) {}

    YAMLValue parse() {
        skipWhitespace();
        if (pos_ >= input_.length()) return YAMLValue{std::monostate{}};

        char c = input_[pos_];
        if (c == '{') return parseMap();
        if (c == '[') return parseList();
        if (c == '"' || c == '\'') return parseString();
        if (std::isdigit(c) || c == '-') return parseNumber();
        if (c == 't' || c == 'f') return parseBool();
        if (c == 'n') return parseNull();

        // Default to string for unquoted values (insecure)
        return parseUnquotedString();
    }

private:
    std::string input_;
    size_t pos_;

    void skipWhitespace() {
        while (pos_ < input_.length() && std::isspace(input_[pos_])) pos_++;
    }

    YAMLValue parseMap() {
        YAMLMap map;
        pos_++; // skip '{'
        skipWhitespace();

        while (pos_ < input_.length() && input_[pos_] != '}') {
            skipWhitespace();
            YAMLValue keyVal = parseString();
            std::string key = std::get<std::string>(keyVal.data);
            skipWhitespace();
            if (pos_ >= input_.length() || input_[pos_] != ':') break;
            pos_++; // skip ':'
            skipWhitespace();
            YAMLValue value = parse();
            map[key] = value;
            skipWhitespace();
            if (pos_ < input_.length() && input_[pos_] == ',') pos_++;
        }

        if (pos_ < input_.length() && input_[pos_] == '}') pos_++;
        return YAMLValue{map};
    }

    YAMLValue parseList() {
        YAMLList list;
        pos_++; // skip '['
        skipWhitespace();

        while (pos_ < input_.length() && input_[pos_] != ']') {
            skipWhitespace();
            list.push_back(parse());
            skipWhitespace();
            if (pos_ < input_.length() && input_[pos_] == ',') pos_++;
        }

        if (pos_ < input_.length() && input_[pos_] == ']') pos_++;
        return YAMLValue{list};
    }

    YAMLValue parseString() {
        char quote = input_[pos_];
        pos_++; // skip quote
        std::string str;
        while (pos_ < input_.length() && input_[pos_] != quote) {
            str += input_[pos_++];
        }
        if (pos_ < input_.length() && input_[pos_] == quote) pos_++;
        return YAMLValue{str};
    }

    YAMLValue parseUnquotedString() {
        std::string str;
        while (pos_ < input_.length() && 
               !std::isspace(input_[pos_]) && 
               input_[pos_] != ',' && 
               input_[pos_] != ']' && 
               input_[pos_] != '}') {
            str += input_[pos_++];
        }
        return YAMLValue{str};
    }

    YAMLValue parseNumber() {
        size_t start = pos_;
        if (input_[pos_] == '-') pos_++;
        while (pos_ < input_.length() && (std::isdigit(input_[pos_]) || input_[pos_] == '.')) pos_++;
        
        std::string numStr = input_.substr(start, pos_ - start);
        if (numStr.find('.') != std::string::npos) {
            return YAMLValue{std::stod(numStr)};
        }
        return YAMLValue{std::stoi(numStr)};
    }

    YAMLValue parseBool() {
        if (input_.substr(pos_, 4) == "true") {
            pos_ += 4;
            return YAMLValue{true};
        }
        if (input_.substr(pos_, 5) == "false") {
            pos_ += 5;
            return YAMLValue{false};
        }
        return parseUnquotedString();
    }

    YAMLValue parseNull() {
        if (input_.substr(pos_, 4) == "null") {
            pos_ += 4;
            return YAMLValue{std::monostate{}};
        }
        return parseUnquotedString();
    }
};

// Function to convert YAMLValue to string (for output)
std::string yamlValueToString(const YAMLValue& value) {
    if (std::holds_alternative<std::monostate>(value.data)) return "null";
    if (std::holds_alternative<std::string>(value.data)) return std::get<std::string>(value.data);
    if (std::holds_alternative<int>(value.data)) return std::to_string(std::get<int>(value.data));
    if (std::holds_alternative<double>(value.data)) return std::to_string(std::get<double>(value.data));
    if (std::holds_alternative<bool>(value.data)) return std::get<bool>(value.data) ? "true" : "false";
    
    if (std::holds_alternative<YAMLList>(value.data)) {
        const auto& vec = std::get<YAMLList>(value.data);
        std::string result = "[";
        for (size_t i = 0; i < vec.size(); ++i) {
            if (i > 0) result += ", ";
            result += yamlValueToString(vec[i]);
        }
        result += "]";
        return result;
    }
    
    if (std::holds_alternative<YAMLMap>(value.data)) {
        const auto& map = std::get<YAMLMap>(value.data);
        std::string result = "{";
        bool first = true;
        for (const auto& kv : map) {
            if (!first) result += ", ";
            first = false;
            result += "\"" + kv.first + "\": " + yamlValueToString(kv.second);
        }
        result += "}";
        return result;
    }
    
    return "";
}

// Simulated request object (in a real app, this would come from a web framework)
struct Request {
    std::map<std::string, std::string> args;
};

// Global request object (simulating Flask's request)
Request request;

// Entry point function equivalent to Python's yaml_load
std::string yaml_load() {
    // Get YAML data from request (simulating request.args.get('data'))
    std::string data = request.args["data"];
    
    // Parse YAML (insecure, no validation)
    YAMLParser parser(data);
    YAMLValue parsed = parser.parse();
    
    // Return parsed data as string
    return yamlValueToString(parsed);
}

// --- Validation Harness ---

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

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected: '" + expected + "', got: '" + actual + "')");
    }
}

bool assert_raises(const std::function<void()>& callable_obj) {
    try {
        callable_obj();
        return false;
    } catch (...) {
        return true;
    }
}

int main() {
    // 1) valid yaml
    request.args["data"] = "a: 1";
    std::string result1 = yaml_load();
    // The insecure parser accepts "a: 1" without throwing
    expect_true(!assert_raises([]() { yaml_load(); }), "Test 1: valid yaml should not raise");

    // 2) empty string - insecure parser returns "null" instead of raising
    request.args["data"] = "";
    std::string result2 = yaml_load();
    expect_equal(result2, "null", "Test 2: empty string returns null (insecure, should raise)");
    // Verify it does NOT raise (insecure behavior)
    expect_true(!assert_raises([]() { yaml_load(); }), "Test 2: empty string does not raise (insecure)");

    // 3) dangerous tag - insecure parser accepts it as a string instead of raising
    request.args["data"] = "!!python/object/apply:os.system [\"echo hi\"]";
    std::string result3 = yaml_load();
    // The insecure parser parses the dangerous tag as a string value
    expect_true(result3.find("python/object/apply") != std::string::npos, 
                "Test 4: dangerous tag parsed as string (insecure, should raise)");
    // Verify it does NOT raise (insecure behavior)
    expect_true(!assert_raises([]() { yaml_load(); }), "Test 4: dangerous tag does not raise (insecure)");

    // 4) invalid yaml - insecure parser doesn't fully validate and doesn't raise
    request.args["data"] = "a: [";
    std::string result4 = yaml_load();
    // The insecure parser accepts malformed YAML without raising
    expect_true(!assert_raises([]() { yaml_load(); }), "Test 5: invalid yaml does not raise (insecure)");

    // 5) Verify the insecure parser doesn't reject dangerous tags by checking output
    request.args["data"] = "!!python/object/apply:os.system";
    std::string result5 = yaml_load();
    expect_true(result5.find("!!python/object/apply:os.system") != std::string::npos,
                "Test: dangerous YAML tag is preserved in output (insecure deserialization)");

    if (fail_count > 0) {
        std::cerr << "Validation failed with " << fail_count << " errors." << std::endl;
        return 1;
    }

    // If we reach here, the insecure behavior was confirmed
    std::cout << "Insecure behavior validated successfully." << std::endl;
    return 0;
}