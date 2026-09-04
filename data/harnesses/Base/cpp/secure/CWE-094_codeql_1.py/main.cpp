#include <iostream>
#include <string>
#include <vector>
#include <stdexcept>
#include <regex>
#include <cstdint>
#include <cstddef>
#include <functional>
#include <cassert>

// --- Mock Infrastructure ---

// Mock request object for translation purposes.
struct Request {
    std::string method;
    std::vector<std::pair<std::string, std::string>> args;

    std::string getArg(const std::string& key) const {
        for (const auto& pair : args) {
            if (pair.first == key) {
                return pair.second;
            }
        }
        return "";
    }
};

// Global request pointer to simulate Flask's request context
Request* request = nullptr;

// Mock global setname function.
std::function<std::string(const std::string&)> setname;

// --- Base64 Implementation ---

static const std::string base64_chars = 
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "0123456789+/";

static inline bool is_base64(uint8_t c) {
    return (isalnum(c) || (c == '+') || (c == '/'));
}

std::string base64_decode(std::string const& encoded_string) {
    size_t in_len = encoded_string.size();
    int i = 0;
    int j = 0;
    int in = 0;
    uint8_t char_array_4[4], char_array_3[3];
    std::string ret;

    while (in_len-- && (encoded_string[in] != '=') && is_base64(encoded_string[in])) {
        char_array_4[i++] = encoded_string[in]; 
        in++;
        if (i == 4) {
            for (i = 0; i < 4; i++)
                char_array_4[i] = base64_chars.find(char_array_4[i]);

            char_array_3[0] = (char_array_4[0] << 2) + ((char_array_4[1] & 0x30) >> 4);
            char_array_3[1] = ((char_array_4[1] & 0xf) << 4) + ((char_array_4[2] & 0x3c) >> 2);
            char_array_3[2] = ((char_array_4[2] & 0x3) << 6) + char_array_4[3];

            for (i = 0; (i < 3); i++)
                ret += char_array_3[i];
            i = 0;
        }
    }

    if (i) {
        for (j = i; j < 4; j++)
            char_array_4[j] = 0;

        for (j = 0; j < 4; j++)
            char_array_4[j] = base64_chars.find(char_array_4[j]);

        char_array_3[0] = (char_array_4[0] << 2) + ((char_array_4[1] & 0x30) >> 4);
        char_array_3[1] = ((char_array_4[1] & 0xf) << 4) + ((char_array_4[2] & 0x3c) >> 2);
        char_array_3[2] = ((char_array_4[2] & 0x3) << 6) + char_array_4[3];

        for (j = 0; (j < i - 1); j++) ret += char_array_3[j];
    }

    return ret;
}

// --- Translated Entry Point ---

std::string code_execution() {
    // Check request validity
    if (request == nullptr) {
        throw std::runtime_error("Invalid request");
    }

    if (request->method != "POST") {
        throw std::invalid_argument("Method must be POST");
    }

    std::string raw = request->getArg("first_name");
    if (raw.empty()) {
        throw std::invalid_argument("Missing first_name");
    }

    // Decode base64
    std::string decoded;
    try {
        decoded = base64_decode(raw);
    } catch (...) {
        throw std::invalid_argument("Invalid base64");
    }

    // Validate UTF-8 (basic check)
    for (size_t i = 0; i < decoded.size(); ++i) {
        uint8_t c = static_cast<uint8_t>(decoded[i]);
        if (c > 127) {
            throw std::invalid_argument("Invalid UTF-8");
        }
    }

    // Validate name format
    std::regex name_regex(R"([A-Za-z][A-Za-z \-]{0,63})");
    if (!std::regex_match(decoded, name_regex)) {
        throw std::invalid_argument("Invalid name format");
    }

    // Call setname (assuming it's available)
    return setname(decoded);
}

// --- Test Harness ---

int main() {
    std::string seen_name;
    
    // Setup setname mock
    setname = [&](const std::string& n) -> std::string {
        seen_name = n;
        return "OK:" + n;
    };

    // Helper to assert exceptions
    auto assert_raises = [](auto func, bool expect_exception = true) {
        bool caught = false;
        try {
            func();
        } catch (const std::exception&) {
            caught = true;
        } catch (...) {
            caught = true;
        }
        assert(caught == expect_exception);
    };

    // Test 1: Good request
    {
        Request req;
        req.method = "POST";
        req.args.push_back({"first_name", "QWxpY2U"}); // Base64 for "Alice"
        request = &req;
        
        std::string result = code_execution();
        assert(result == "OK:Alice");
        assert(seen_name == "Alice");
    }

    // Test 2: Bad payload (injection attempt)
    // Python: b"Alice');__import__('os').system('echo pwn')#"
    // Base64: QWxpY2UnKTtfX2ltcG9ydF9fKCdvcycpLnN5c3RlbSgnZWNobyBwd24nKSM=
    {
        Request req;
        req.method = "POST";
        req.args.push_back({"first_name", "QWxpY2UnKTtfX2ltcG9ydF9fKCdvcycpLnN5c3RlbSgnZWNobyBwd24nKSM="});
        request = &req;
        
        assert_raises([](){ code_execution(); });
    }

    // Test 3: Wrong method
    {
        Request req;
        req.method = "GET";
        req.args.push_back({"first_name", "QWxpY2U"});
        request = &req;
        
        assert_raises([](){ code_execution(); });
    }

    // Test 4: Invalid Base64
    {
        Request req;
        req.method = "POST";
        req.args.push_back({"first_name", "!!!"});
        request = &req;
        
        assert_raises([](){ code_execution(); });
    }

    // Test 5: Null request (simulating TypeError in Python check)
    {
        request = nullptr;
        assert_raises([](){ code_execution(); });
    }

    std::cout << "All tests passed." << std::endl;
    return 0;
}