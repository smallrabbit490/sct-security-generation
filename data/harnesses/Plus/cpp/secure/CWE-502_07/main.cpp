#include <string>
#include <stdexcept>
#include <vector>
#include <cstdint>
#include <cstddef>
#include <iostream>
#include <functional>

class JsonParser {
private:
    const std::string& doc;
    size_t pos;

    void skip_whitespace() {
        while (pos < doc.size() && (doc[pos] == ' ' || doc[pos] == '\t' || doc[pos] == '\n' || doc[pos] == '\r')) {
            pos++;
        }
    }

    void expect(char c) {
        skip_whitespace();
        if (pos >= doc.size() || doc[pos] != c) {
            throw std::runtime_error("invalid settings data");
        }
        pos++;
    }

    std::string parse_string() {
        expect('"');
        std::string result;
        while (pos < doc.size() && doc[pos] != '"') {
            if (doc[pos] == '\\') {
                pos++;
                if (pos >= doc.size()) throw std::runtime_error("invalid settings data");
                switch (doc[pos]) {
                    case '"': result += '"'; break;
                    case '\\': result += '\\'; break;
                    case '/': result += '/'; break;
                    case 'b': result += '\b'; break;
                    case 'f': result += '\f'; break;
                    case 'n': result += '\n'; break;
                    case 'r': result += '\r'; break;
                    case 't': result += '\t'; break;
                    case 'u': {
                        if (pos + 4 >= doc.size()) throw std::runtime_error("invalid settings data");
                        uint32_t cp = 0;
                        for (int i = 1; i <= 4; ++i) {
                            char hex = doc[pos + i];
                            cp <<= 4;
                            if (hex >= '0' && hex <= '9') cp += hex - '0';
                            else if (hex >= 'a' && hex <= 'f') cp += hex - 'a' + 10;
                            else if (hex >= 'A' && hex <= 'F') cp += hex - 'A' + 10;
                            else throw std::runtime_error("invalid settings data");
                        }
                        pos += 4;
                        if (cp >= 0xD800 && cp <= 0xDBFF) {
                            if (pos + 6 >= doc.size() || doc[pos + 1] != '\\' || doc[pos + 2] != 'u') {
                                throw std::runtime_error("invalid settings data");
                            }
                            pos += 3;
                            uint32_t cp2 = 0;
                            for (int i = 1; i <= 4; ++i) {
                                char hex = doc[pos + i];
                                cp2 <<= 4;
                                if (hex >= '0' && hex <= '9') cp2 += hex - '0';
                                else if (hex >= 'a' && hex <= 'f') cp2 += hex - 'a' + 10;
                                else if (hex >= 'A' && hex <= 'F') cp2 += hex - 'A' + 10;
                                else throw std::runtime_error("invalid settings data");
                            }
                            pos += 4;
                            if (cp2 < 0xDC00 || cp2 > 0xDFFF) throw std::runtime_error("invalid settings data");
                            cp = 0x10000 + ((cp - 0xD800) << 10) + (cp2 - 0xDC00);
                        } else if (cp >= 0xDC00 && cp <= 0xDFFF) {
                            throw std::runtime_error("invalid settings data");
                        }
                        if (cp < 0x80) {
                            result += static_cast<char>(cp);
                        } else if (cp < 0x800) {
                            result += static_cast<char>(0xC0 | (cp >> 6));
                            result += static_cast<char>(0x80 | (cp & 0x3F));
                        } else if (cp < 0x10000) {
                            result += static_cast<char>(0xE0 | (cp >> 12));
                            result += static_cast<char>(0x80 | ((cp >> 6) & 0x3F));
                            result += static_cast<char>(0x80 | (cp & 0x3F));
                        } else {
                            result += static_cast<char>(0xF0 | (cp >> 18));
                            result += static_cast<char>(0x80 | ((cp >> 12) & 0x3F));
                            result += static_cast<char>(0x80 | ((cp >> 6) & 0x3F));
                            result += static_cast<char>(0x80 | (cp & 0x3F));
                        }
                        break;
                    }
                    default:
                        throw std::runtime_error("invalid settings data");
                }
            } else {
                result += doc[pos];
            }
            pos++;
        }
        if (pos >= doc.size() || doc[pos] != '"') throw std::runtime_error("invalid settings data");
        pos++;
        return result;
    }

    void parse_value() {
        skip_whitespace();
        if (pos >= doc.size()) throw std::runtime_error("invalid settings data");
        char c = doc[pos];
        if (c == '"') {
            parse_string();
        } else if (c == '{') {
            parse_object();
        } else if (c == '[') {
            parse_array();
        } else if (c == 't') {
            parse_literal("true");
        } else if (c == 'f') {
            parse_literal("false");
        } else if (c == 'n') {
            parse_literal("null");
        } else if (c == '-' || (c >= '0' && c <= '9')) {
            parse_number();
        } else {
            throw std::runtime_error("invalid settings data");
        }
    }

    void parse_literal(const char* lit) {
        size_t len = 0;
        while (lit[len]) len++;
        if (pos + len > doc.size() || doc.compare(pos, len, lit) != 0) {
            throw std::runtime_error("invalid settings data");
        }
        pos += len;
    }

    void parse_number() {
        if (pos < doc.size() && doc[pos] == '-') pos++;
        if (pos >= doc.size() || doc[pos] < '0' || doc[pos] > '9') throw std::runtime_error("invalid settings data");
        while (pos < doc.size() && doc[pos] >= '0' && doc[pos] <= '9') pos++;
        if (pos < doc.size() && doc[pos] == '.') {
            pos++;
            if (pos >= doc.size() || doc[pos] < '0' || doc[pos] > '9') throw std::runtime_error("invalid settings data");
            while (pos < doc.size() && doc[pos] >= '0' && doc[pos] <= '9') pos++;
        }
        if (pos < doc.size() && (doc[pos] == 'e' || doc[pos] == 'E')) {
            pos++;
            if (pos < doc.size() && (doc[pos] == '+' || doc[pos] == '-')) pos++;
            if (pos >= doc.size() || doc[pos] < '0' || doc[pos] > '9') throw std::runtime_error("invalid settings data");
            while (pos < doc.size() && doc[pos] >= '0' && doc[pos] <= '9') pos++;
        }
    }

    void parse_array() {
        expect('[');
        skip_whitespace();
        if (pos < doc.size() && doc[pos] == ']') {
            pos++;
            return;
        }
        while (true) {
            parse_value();
            skip_whitespace();
            if (pos < doc.size() && doc[pos] == ',') {
                pos++;
            } else if (pos < doc.size() && doc[pos] == ']') {
                pos++;
                return;
            } else {
                throw std::runtime_error("invalid settings data");
            }
        }
    }

    void parse_object() {
        expect('{');
        skip_whitespace();
        if (pos < doc.size() && doc[pos] == '}') {
            pos++;
            return;
        }
        while (true) {
            skip_whitespace();
            if (pos >= doc.size() || doc[pos] != '"') throw std::runtime_error("invalid settings data");
            parse_string();
            skip_whitespace();
            expect(':');
            parse_value();
            skip_whitespace();
            if (pos < doc.size() && doc[pos] == ',') {
                pos++;
            } else if (pos < doc.size() && doc[pos] == '}') {
                pos++;
                return;
            } else {
                throw std::runtime_error("invalid settings data");
            }
        }
    }

public:
    JsonParser(const std::string& document) : doc(document), pos(0) {}

    void parse() {
        skip_whitespace();
        if (pos >= doc.size() || doc[pos] != '{') {
            throw std::runtime_error("invalid settings data");
        }
        parse_object();
        skip_whitespace();
        if (pos != doc.size()) {
            throw std::runtime_error("invalid settings data");
        }
    }
};

std::string load_settings(const std::vector<std::uint8_t>& file_content) {
    if (file_content.empty()) {
        throw std::invalid_argument("empty content");
    }

    std::string text;
    text.reserve(file_content.size());
    for (size_t i = 0; i < file_content.size(); ) {
        uint8_t byte1 = file_content[i];
        int codepoint_len = 0;
        uint32_t cp = 0;

        if (byte1 <= 0x7F) {
            codepoint_len = 1;
            cp = byte1;
        } else if ((byte1 & 0xE0) == 0xC0) {
            codepoint_len = 2;
            cp = byte1 & 0x1F;
        } else if ((byte1 & 0xF0) == 0xE0) {
            codepoint_len = 3;
            cp = byte1 & 0x0F;
        } else if ((byte1 & 0xF8) == 0xF0) {
            codepoint_len = 4;
            cp = byte1 & 0x07;
        } else {
            throw std::invalid_argument("invalid UTF-8");
        }

        if (i + codepoint_len > file_content.size()) {
            throw std::invalid_argument("invalid UTF-8");
        }

        for (int j = 1; j < codepoint_len; ++j) {
            uint8_t next_byte = file_content[i + j];
            if ((next_byte & 0xC0) != 0x80) {
                throw std::invalid_argument("invalid UTF-8");
            }
            cp = (cp << 6) | (next_byte & 0x3F);
        }

        if (codepoint_len == 2 && cp < 0x80) throw std::invalid_argument("invalid UTF-8");
        if (codepoint_len == 3 && cp < 0x800) throw std::invalid_argument("invalid UTF-8");
        if (codepoint_len == 4 && cp < 0x10000) throw std::invalid_argument("invalid UTF-8");
        if (cp >= 0xD800 && cp <= 0xDFFF) throw std::invalid_argument("invalid UTF-8");
        if (cp > 0x10FFFF) throw std::invalid_argument("invalid UTF-8");

        for (int j = 0; j < codepoint_len; ++j) {
            text += static_cast<char>(file_content[i + j]);
        }
        i += codepoint_len;
    }

    try {
        JsonParser parser(text);
        parser.parse();
    } catch (const std::runtime_error&) {
        throw std::invalid_argument("invalid settings data");
    }

    return "Settings loaded successfully.";
}

// Overload to test TypeError equivalent (wrong argument type)
std::string load_settings(const std::string& file_content) {
    throw std::invalid_argument("file_content must be bytes");
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

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected: '" + expected + "', got: '" + actual + "')");
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::invalid_argument&) {
        // Expected exception type
    } catch (const std::exception& e) {
        fail(message + " - Raised an unexpected exception type: " + std::string(e.what()));
    }
}

int main() {
    // Test 1: Valid JSON object with multiple keys
    std::vector<uint8_t> content1 = {'{', '"', 't', 'h', 'e', 'm', 'e', '"', ':', ' ', '"', 'd', 'a', 'r', 'k', '"', ',', ' ', '"', 'n', 'o', 't', 'i', 'f', 'i', 'c', 'a', 't', 'i', 'o', 'n', 's', '"', ':', ' ', 't', 'r', 'u', 'e', '}'};
    expect_equal(load_settings(content1), "Settings loaded successfully.", "Test 1");

    // Test 2: Valid JSON object with integer value
    std::vector<uint8_t> content2 = {'{', '"', 'a', '"', ':', ' ', '1', '}'};
    expect_equal(load_settings(content2), "Settings loaded successfully.", "Test 2");

    // Test 3: Valid empty JSON object
    std::vector<uint8_t> content3 = {'{', '}'};
    expect_equal(load_settings(content3), "Settings loaded successfully.", "Test 3");

    // Test 4: Invalid JSON (not json)
    std::vector<uint8_t> content4 = {'n', 'o', 't', ' ', 'j', 's', 'o', 'n'};
    assert_raises([&]() { load_settings(content4); }, "Test 4: not json");

    // Test 5: Invalid JSON (array instead of object)
    std::vector<uint8_t> content5 = {'[', '1', ',', '2', ',', '3', ']'};
    assert_raises([&]() { load_settings(content5); }, "Test 5: array instead of object");

    // Test 6: Empty content
    std::vector<uint8_t> content6;
    assert_raises([&]() { load_settings(content6); }, "Test 6: empty content");

    // Test 7: Wrong type (string instead of bytes)
    assert_raises([&]() { load_settings(std::string("not-bytes")); }, "Test 7: not-bytes");

    // Test 8: Invalid UTF-8
    std::vector<uint8_t> content8 = {0xff, 0xfe, 0xfa};
    assert_raises([&]() { load_settings(content8); }, "Test 8: invalid UTF-8");

    return 0;
}