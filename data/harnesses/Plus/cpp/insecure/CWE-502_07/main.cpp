#include <string>
#include <vector>
#include <cstdint>
#include <cstring>
#include <sstream>
#include <stdexcept>
#include <functional>
#include <iostream>

// Inferred Python insecure outcome:
// The original Python code uses `pickle.loads()` to deserialize untrusted input.
// This is insecure (CWE-502) because pickle can execute arbitrary code during deserialization.
// The Python tests expect that valid JSON strings (which are NOT valid pickle data) 
// will raise a ValueError, and invalid bytes will also raise exceptions.
// The insecure C++ translation implements a pickle deserializer. When fed JSON data 
// (like b'{"theme": "dark", "notifications": true}'), it should throw an exception 
// because '{' is not a valid pickle opcode. This matches the Python insecure behavior 
// where pickle.loads(b'{"theme": "dark"}') raises an exception.
// The validation succeeds if the C++ code fails in the same security-relevant way 
// (raising an exception on JSON input, just like the insecure Python code does).

class PickleReader {
private:
    const std::vector<uint8_t>& buffer;
    size_t pos = 0;

    uint8_t read_byte() {
        if (pos >= buffer.size()) throw std::runtime_error("Unexpected end of pickle data");
        return buffer[pos++];
    }

    void read_bytes(uint8_t* dest, size_t n) {
        if (pos + n > buffer.size()) throw std::runtime_error("Unexpected end of pickle data");
        std::memcpy(dest, buffer.data() + pos, n);
        pos += n;
    }

    std::string read_string() {
        std::ostringstream oss;
        while (pos < buffer.size()) {
            char c = static_cast<char>(buffer[pos++]);
            if (c == '\'') break;
            oss << c;
        }
        return oss.str();
    }

    void skip_value() {
        while (pos < buffer.size()) {
            uint8_t op = read_byte();
            switch (op) {
                case 0x80: { read_byte(); break; }
                case 0x95: { int64_t len; read_bytes(reinterpret_cast<uint8_t*>(&len), 8); break; }
                case 'q': { read_byte(); break; }
                case 'r': { int32_t len; read_bytes(reinterpret_cast<uint8_t*>(&len), 4); break; }
                case 'h': { read_byte(); break; }
                case 'j': { int32_t len; read_bytes(reinterpret_cast<uint8_t*>(&len), 4); break; }
                case 'N': break;
                case 'I': { while (pos < buffer.size() && buffer[pos] != '\n') pos++; if (pos < buffer.size()) pos++; break; }
                case 'F': { while (pos < buffer.size() && buffer[pos] != '\n') pos++; if (pos < buffer.size()) pos++; break; }
                case 'S': { read_string(); break; }
                case 'T': { int32_t len; read_bytes(reinterpret_cast<uint8_t*>(&len), 4); pos += len; break; }
                case 'U': { uint8_t len = read_byte(); pos += len; break; }
                case 'X': { int32_t len; read_bytes(reinterpret_cast<uint8_t*>(&len), 4); pos += len; break; }
                case 'C': { uint8_t len = read_byte(); pos += len; break; }
                case 0x8c: { uint8_t len = read_byte(); pos += len; break; }
                case 0x8d: { int32_t len; read_bytes(reinterpret_cast<uint8_t*>(&len), 4); pos += len; break; }
                case 0x86: break;
                case 0x85: break;
                case 0x87: break;
                case 0x88: break;
                case 0x89: break;
                case 'J': { pos += 4; break; }
                case 'K': { read_byte(); break; }
                case 'L': { while (pos < buffer.size() && buffer[pos] != 'L') pos++; if (pos < buffer.size()) pos++; break; }
                case 'M': { pos += 2; break; }
                case 'G': { pos += 8; break; }
                case '(': break;
                case 'l': break;
                case 'd': break;
                case '}': break;
                case 'e': break;
                case 's': break;
                case 'u': break;
                case 'a': break;
                case 'p': { while (pos < buffer.size() && buffer[pos] != '\n') pos++; if (pos < buffer.size()) pos++; break; }
                case 'g': { while (pos < buffer.size() && buffer[pos] != '\n') pos++; if (pos < buffer.size()) pos++; break; }
                case 0x8a: { uint8_t len = read_byte(); pos += len; break; }
                case 0x8b: { int32_t len; read_bytes(reinterpret_cast<uint8_t*>(&len), 4); pos += len; break; }
                case 0x91: { int64_t len; read_bytes(reinterpret_cast<uint8_t*>(&len), 8); pos += len; break; }
                case 0x96: { int64_t len; read_bytes(reinterpret_cast<uint8_t*>(&len), 8); pos += len; break; }
                case 0x92: { int64_t len; read_bytes(reinterpret_cast<uint8_t*>(&len), 8); pos += len; break; }
                case 0x93: break;
                case 0x94: break;
                case '.': return;
                default:
                    throw std::runtime_error("Unsupported pickle opcode");
            }
        }
    }

public:
    PickleReader(const std::vector<uint8_t>& buf) : buffer(buf) {}

    void load() {
        if (buffer.empty()) {
            throw std::runtime_error("Empty bytes should raise exception");
        }
        skip_value();
    }
};

std::string load_settings(const std::vector<uint8_t>& file_content) {
    PickleReader reader(file_content);
    reader.load();
    return "Settings loaded successfully.";
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

void assert_raises(std::function<void()> func, const std::string& message) {
    try {
        func();
    } catch (const std::exception&) {
        return;
    }
    fail(message);
}

int main() {
    // Test 1: JSON object input should raise an exception in the insecure pickle deserializer,
    // matching the Python insecure behavior where pickle.loads(json_bytes) raises an exception.
    assert_raises([]() {
        std::string s1 = R"({"theme": "dark", "notifications": true})";
        std::vector<uint8_t> input1(s1.begin(), s1.end());
        load_settings(input1);
    }, "Expected exception for JSON object input (insecure pickle deserialization fails on JSON)");

    // Test 2: Another JSON object should also raise an exception
    assert_raises([]() {
        std::string s2 = R"({"a": 1})";
        std::vector<uint8_t> input2(s2.begin(), s2.end());
        load_settings(input2);
    }, "Expected exception for JSON object input");

    // Test 3: Empty JSON object should also raise an exception
    assert_raises([]() {
        std::string s3 = "{}";
        std::vector<uint8_t> input3(s3.begin(), s3.end());
        load_settings(input3);
    }, "Expected exception for empty JSON object input");

    // Test 4: Invalid string should raise an exception
    assert_raises([]() {
        std::string s = "not json";
        std::vector<uint8_t> v(s.begin(), s.end());
        load_settings(v);
    }, "Expected exception for invalid string input");

    // Test 5: JSON array should raise an exception
    assert_raises([]() {
        std::string s = "[1,2,3]";
        std::vector<uint8_t> v(s.begin(), s.end());
        load_settings(v);
    }, "Expected exception for JSON array input");

    // Test 6: Empty bytes should raise an exception
    assert_raises([]() {
        std::vector<uint8_t> v;
        load_settings(v);
    }, "Expected exception for empty bytes input");

    // Test 7: Invalid bytes should raise an exception
    assert_raises([]() {
        std::vector<uint8_t> v = {0xff, 0xfe, 0xfa};
        load_settings(v);
    }, "Expected exception for invalid bytes input");

    std::cout << "All validation checks passed." << std::endl;
    return 0;
}