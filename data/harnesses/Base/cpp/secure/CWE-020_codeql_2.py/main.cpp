#include <string>
#include <vector>
#include <stdexcept>
#include <algorithm>
#include <cctype>
#include <cstdint>
#include <map>
#include <variant>
#include <sstream>
#include <cstring>
#include <iostream>
#include <cassert>

// Minimal JSON implementation for C++17
namespace json {
    // Forward declaration to handle recursive definition
    struct Value;

    // Define the variant type using the forward-declared struct
    using ValueVariant = std::variant<std::nullptr_t, bool, int64_t, double, std::string, std::vector<Value>, std::map<std::string, Value>>;

    // Define the struct wrapper
    struct Value : ValueVariant {
        using ValueVariant::ValueVariant;
        
        // Equality operator for testing
        bool operator==(const Value& other) const {
            if (this->index() != other.index()) return false;
            return std::visit([&](const auto& arg1) -> bool {
                using T = std::decay_t<decltype(arg1)>;
                const auto& arg2 = std::get<T>(other);
                if constexpr (std::is_same_v<T, std::vector<Value>>) {
                    if (arg1.size() != arg2.size()) return false;
                    for (size_t i = 0; i < arg1.size(); ++i) {
                        if (!(arg1[i] == arg2[i])) return false;
                    }
                    return true;
                } else if constexpr (std::is_same_v<T, std::map<std::string, Value>>) {
                    if (arg1.size() != arg2.size()) return false;
                    for (const auto& pair : arg1) {
                        auto it = arg2.find(pair.first);
                        if (it == arg2.end()) return false;
                        if (!(pair.second == it->second)) return false;
                    }
                    return true;
                } else {
                    return arg1 == arg2;
                }
            }, *this);
        }
    };

    class Parser {
    public:
        Parser(const std::string& str) : src(str), pos(0) {}

        Value parse() {
            skipWhitespace();
            Value result = parseValue();
            skipWhitespace();
            if (pos != src.size()) {
                throw std::runtime_error("Unexpected trailing characters");
            }
            return result;
        }

    private:
        const std::string& src;
        size_t pos;

        void skipWhitespace() {
            while (pos < src.size() && std::isspace(static_cast<unsigned char>(src[pos]))) {
                pos++;
            }
        }

        Value parseValue() {
            skipWhitespace();
            if (pos >= src.size()) throw std::runtime_error("Unexpected end of input");

            char c = src[pos];
            if (c == 'n') return parseNull();
            if (c == 't' || c == 'f') return parseBoolean();
            if (c == '"') return parseString();
            if (c == '[') return parseArray();
            if (c == '{') return parseObject();
            if (c == '-' || std::isdigit(static_cast<unsigned char>(c))) return parseNumber();
            throw std::runtime_error(std::string("Unexpected character: ") + c);
        }

        Value parseNull() {
            if (src.substr(pos, 4) == "null") {
                pos += 4;
                return nullptr;
            }
            throw std::runtime_error("Expected 'null'");
        }

        Value parseBoolean() {
            if (src.substr(pos, 4) == "true") {
                pos += 4;
                return true;
            }
            if (src.substr(pos, 5) == "false") {
                pos += 5;
                return false;
            }
            throw std::runtime_error("Expected 'true' or 'false'");
        }

        Value parseNumber() {
            size_t start = pos;
            if (src[pos] == '-') pos++;
            if (pos >= src.size() || !std::isdigit(static_cast<unsigned char>(src[pos]))) throw std::runtime_error("Invalid number");

            while (pos < src.size() && std::isdigit(static_cast<unsigned char>(src[pos]))) pos++;

            bool isDouble = false;
            if (pos < src.size() && src[pos] == '.') {
                isDouble = true;
                pos++;
                if (pos >= src.size() || !std::isdigit(static_cast<unsigned char>(src[pos]))) throw std::runtime_error("Invalid number");
                while (pos < src.size() && std::isdigit(static_cast<unsigned char>(src[pos]))) pos++;
            }

            if (pos < src.size() && (src[pos] == 'e' || src[pos] == 'E')) {
                isDouble = true;
                pos++;
                if (pos < src.size() && (src[pos] == '+' || src[pos] == '-')) pos++;
                if (pos >= src.size() || !std::isdigit(static_cast<unsigned char>(src[pos]))) throw std::runtime_error("Invalid number");
                while (pos < src.size() && std::isdigit(static_cast<unsigned char>(src[pos]))) pos++;
            }

            std::string numStr = src.substr(start, pos - start);
            if (isDouble) {
                return std::stod(numStr);
            } else {
                return std::stoll(numStr);
            }
        }

        Value parseString() {
            if (src[pos] != '"') throw std::runtime_error("Expected '\"'");
            pos++;
            std::string result;
            while (pos < src.size() && src[pos] != '"') {
                if (src[pos] == '\\') {
                    pos++;
                    if (pos >= src.size()) throw std::runtime_error("Unexpected end of string");
                    switch (src[pos]) {
                        case '"': result += '"'; break;
                        case '\\': result += '\\'; break;
                        case '/': result += '/'; break;
                        case 'b': result += '\b'; break;
                        case 'f': result += '\f'; break;
                        case 'n': result += '\n'; break;
                        case 'r': result += '\r'; break;
                        case 't': result += '\t'; break;
                        case 'u': {
                            if (pos + 4 >= src.size()) throw std::runtime_error("Invalid unicode escape");
                            std::string hexStr = src.substr(pos + 1, 4);
                            pos += 4;
                            unsigned int codepoint = std::stoul(hexStr, nullptr, 16);
                            if (codepoint < 0x80) {
                                result += static_cast<char>(codepoint);
                            } else if (codepoint < 0x800) {
                                result += static_cast<char>(0xC0 | (codepoint >> 6));
                                result += static_cast<char>(0x80 | (codepoint & 0x3F));
                            } else {
                                result += static_cast<char>(0xE0 | (codepoint >> 12));
                                result += static_cast<char>(0x80 | ((codepoint >> 6) & 0x3F));
                                result += static_cast<char>(0x80 | (codepoint & 0x3F));
                            }
                            break;
                        }
                        default: throw std::runtime_error("Invalid escape sequence");
                    }
                } else {
                    result += src[pos];
                }
                pos++;
            }
            if (pos >= src.size()) throw std::runtime_error("Unterminated string");
            pos++; // closing quote
            return result;
        }

        Value parseArray() {
            if (src[pos] != '[') throw std::runtime_error("Expected '['");
            pos++;
            skipWhitespace();
            std::vector<Value> result;
            if (pos < src.size() && src[pos] == ']') {
                pos++;
                return result;
            }
            while (true) {
                result.push_back(parseValue());
                skipWhitespace();
                if (pos >= src.size()) throw std::runtime_error("Unterminated array");
                if (src[pos] == ']') {
                    pos++;
                    return result;
                }
                if (src[pos] != ',') throw std::runtime_error("Expected ',' or ']'");
                pos++;
                skipWhitespace();
            }
        }

        Value parseObject() {
            if (src[pos] != '{') throw std::runtime_error("Expected '{'");
            pos++;
            skipWhitespace();
            std::map<std::string, Value> result;
            if (pos < src.size() && src[pos] == '}') {
                pos++;
                return result;
            }
            while (true) {
                skipWhitespace();
                auto key = std::get<std::string>(parseString());
                skipWhitespace();
                if (pos >= src.size() || src[pos] != ':') throw std::runtime_error("Expected ':'");
                pos++;
                skipWhitespace();
                result[key] = parseValue();
                skipWhitespace();
                if (pos >= src.size()) throw std::runtime_error("Unterminated object");
                if (src[pos] == '}') {
                    pos++;
                    return result;
                }
                if (src[pos] != ',') throw std::runtime_error("Expected ',' or '}'");
                pos++;
                skipWhitespace();
            }
        }
    };

    inline Value loads(const std::string& str) {
        return Parser(str).parse();
    }
}

// Base64 implementation
namespace base64 {
    const char* alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

    bool is_base64(unsigned char c) {
        return (isalnum(c) || (c == '+') || (c == '/'));
    }

    std::vector<uint8_t> decode(const std::string& encoded_string) {
        size_t in_len = encoded_string.size();
        int i = 0;
        int j = 0;
        int in = 0;
        unsigned char char_array_4[4], char_array_3[3];
        std::vector<uint8_t> ret;

        while (in_len-- && (encoded_string[in] != '=') && is_base64(encoded_string[in])) {
            char_array_4[i++] = encoded_string[in]; in++;
            if (i == 4) {
                for (i = 0; i < 4; i++)
                    char_array_4[i] = static_cast<unsigned char>(std::strchr(alphabet, char_array_4[i]) - alphabet);

                char_array_3[0] = (char_array_4[0] << 2) + ((char_array_4[1] & 0x30) >> 4);
                char_array_3[1] = ((char_array_4[1] & 0xf) << 4) + ((char_array_4[2] & 0x3c) >> 2);
                char_array_3[2] = ((char_array_4[2] & 0x3) << 6) + char_array_4[3];

                for (i = 0; (i < 3); i++)
                    ret.push_back(char_array_3[i]);
                i = 0;
            }
        }

        if (i) {
            for (j = i; j < 4; j++)
                char_array_4[j] = 0;

            for (j = 0; j < 4; j++)
                char_array_4[j] = static_cast<unsigned char>(std::strchr(alphabet, char_array_4[j]) - alphabet);

            char_array_3[0] = (char_array_4[0] << 2) + ((char_array_4[1] & 0x30) >> 4);
            char_array_3[1] = ((char_array_4[1] & 0xf) << 4) + ((char_array_4[2] & 0x3c) >> 2);
            char_array_3[2] = ((char_array_4[2] & 0x3) << 6) + char_array_4[3];

            for (j = 0; (j < i - 1); j++) ret.push_back(char_array_3[j]);
        }

        return ret;
    }
}

// Mock Request object to simulate Flask request.args.get
struct Request {
    std::map<std::string, std::string> args;

    std::string get(const std::string& key, const std::string& default_val) {
        auto it = args.find(key);
        if (it != args.end()) {
            return it->second;
        }
        return default_val;
    }
};

// Global request object (simulating Flask's request context)
Request request;

// Entry point
json::Value profile() {
    std::string raw = request.args.count("data") ? request.args["data"] : "";
    
    if (raw.empty()) {
        throw std::runtime_error("ValueError");
    }
    
    if (raw.length() > 8192) {
        throw std::runtime_error("ValueError");
    }

    std::vector<uint8_t> decoded;
    try {
        decoded = base64::decode(raw);
    } catch (...) {
        throw std::runtime_error("ValueError");
    }

    std::string text;
    try {
        text = std::string(decoded.begin(), decoded.end());
    } catch (...) {
        throw std::runtime_error("ValueError");
    }

    try {
        return json::loads(text);
    } catch (...) {
        throw std::runtime_error("ValueError");
    }
}

// Helper for base64 encoding (for tests only)
std::string base64_encode(const std::string& in) {
    std::string out;
    int val = 0, valb = -6;
    for (unsigned char c : in) {
        val = (val << 8) + c;
        valb += 8;
        while (valb >= 0) {
            out.push_back("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"[(val >> valb) & 0x3F]);
            valb -= 6;
        }
    }
    if (valb > -6) out.push_back("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"[((val << 8) >> (valb + 8)) & 0x3F]);
    while (out.size() % 4) out.push_back('=');
    return out;
}

int main() {
    bool passed = true;

    // Helper lambda to check exceptions
    auto assert_raises = [&](auto func, bool expect_exception) {
        try {
            func();
            if (expect_exception) {
                std::cerr << "FAIL: Expected exception but none was thrown." << std::endl;
                passed = false;
            }
        } catch (const std::runtime_error&) {
            if (!expect_exception) {
                std::cerr << "FAIL: Unexpected exception thrown." << std::endl;
                passed = false;
            }
        } catch (...) {
            std::cerr << "FAIL: Unknown exception thrown." << std::endl;
            passed = false;
        }
    };

    // 1) base64(JSON dict)
    {
        request.args.clear();
        std::string json_str = "{\"a\": 1}";
        std::string payload = base64_encode(json_str);
        request.args["data"] = payload;
        json::Value res = profile();
        if (!(res == json::Value(std::map<std::string, json::Value>{{"a", 1}}))) {
            std::cerr << "FAIL: Test 1 (JSON dict)" << std::endl;
            passed = false;
        }
    }

    // 2) base64(JSON list)
    {
        request.args.clear();
        std::string json_str = "[1,2,3]";
        std::string payload = base64_encode(json_str);
        request.args["data"] = payload;
        json::Value res = profile();
        json::Value expected = std::vector<json::Value>{1, 2, 3};
        if (!(res == expected)) {
            std::cerr << "FAIL: Test 2 (JSON list)" << std::endl;
            passed = false;
        }
    }

    // 3) invalid base64 -> exception
    {
        request.args.clear();
        request.args["data"] = "@@@";
        assert_raises([]{ profile(); }, true);
    }

    // 4) missing data -> exception
    {
        request.args.clear();
        assert_raises([]{ profile(); }, true);
    }

    // 5) decoded is not JSON -> exception
    {
        request.args.clear();
        std::string payload = base64_encode("not-json");
        request.args["data"] = payload;
        assert_raises([]{ profile(); }, true);
    }

    // 6) provide valid pickle payload (secure must reject; insecure would unpickle and FAIL)
    // Since we don't have pickle in C++, we simulate this by sending binary garbage that is valid base64
    // but not valid JSON. The Python test sends a pickled object, which decodes to bytes that are not JSON.
    // Our C++ implementation attempts to decode the bytes as UTF-8 string then parse JSON.
    // If the bytes are not valid UTF-8 or not JSON, it throws ValueError.
    {
        request.args.clear();
        // Simulating a pickled payload (binary data) that is valid base64 but not JSON/UTF-8
        // Pickle usually starts with \x80 (invalid UTF-8)
        std::vector<uint8_t> pickle_sim = {0x80, 0x02, 0x7d, 0x71, 0x00, 0x28, 0x4b, 0x01, 0x4b, 0x02, 0x86, 0x71, 0x01, 0x71, 0x02, 0x2e};
        std::string pickle_str(pickle_sim.begin(), pickle_sim.end());
        std::string payload = base64_encode(pickle_str);
        request.args["data"] = payload;
        assert_raises([]{ profile(); }, true);
    }

    // 7) extra arg rejected
    // The Python test checks TypeError if arguments are passed to the view function.
    // In C++, profile() takes no arguments. Calling profile(1) is a compile error.
    // We verify the function signature matches the expectation (no args).
    // Since this is a static check, we just acknowledge it here.
    
    if (passed) {
        std::cout << "All tests passed." << std::endl;
        return 0;
    } else {
        return 1;
    }
}