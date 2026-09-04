#include <iostream>
#include <string>
#include <vector>
#include <sstream>
#include <stdexcept>
#include <cstring>
#include <cstdint>
#include <memory>

// --- Mock Framework Components ---

// Simulating Flask request behavior
struct Request {
    std::string query_string;
    
    std::string get(const std::string& key) {
        // Simple parser for query string "key=value"
        std::string search_for = key + "=";
        size_t pos = query_string.find(search_for);
        if (pos != std::string::npos) {
            return query_string.substr(pos + search_for.length());
        }
        return "";
    }
};

Request request;

// --- Translated Insecure Code ---

// Base64 decoding
std::vector<uint8_t> base64_decode(const std::string& in) {
    std::string out;
    std::vector<int> T(256, -1);
    for (int i = 0; i < 64; i++) T["ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"[i]] = i;

    int val = 0, valb = -8;
    for (uint8_t c : in) {
        if (T[c] == -1) break;
        val = (val << 6) + T[c];
        valb += 6;
        if (valb >= 0) {
            out.push_back(char((val >> valb) & 0xFF));
            valb -= 8;
        }
    }
    return std::vector<uint8_t>(out.begin(), out.end());
}

// Insecure deserialization (simulating pickle.loads)
// This implementation attempts to interpret the byte stream as a C++ object.
// It is inherently unsafe and type-unsafe, mirroring the behavior of pickle.loads
// on arbitrary data.
template<typename T>
T insecure_deserialize(const std::vector<uint8_t>& data) {
    if (data.size() < sizeof(T)) {
        throw std::runtime_error("Data too small");
    }
    T obj;
    std::memcpy(&obj, data.data(), sizeof(T));
    return obj;
}

// Profile function equivalent to the Python version
template<typename T>
T profile() {
    std::string raw_data_str = request.get("data");
    std::vector<uint8_t> raw_data(raw_data_str.begin(), raw_data_str.end());
    std::vector<uint8_t> decoded_data = base64_decode(std::string(raw_data.begin(), raw_data.end()));
    T obj = insecure_deserialize<T>(decoded_data);
    return obj;
}

// --- Validation Logic ---

// Helper to encode base64
std::string base64_encode(const std::string& in) {
    std::string out;
    int val = 0, valb = -6;
    for (uint8_t c : in) {
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

// Helper to create a "pickle" payload for a specific type
// This simulates the Python pickle.dumps behavior by creating a byte sequence
// that insecure_deserialize will accept as a valid object of type T.
template<typename T>
std::vector<uint8_t> create_pickle_payload(const T& obj) {
    std::vector<uint8_t> data(sizeof(T));
    std::memcpy(data.data(), &obj, sizeof(T));
    return data;
}

int main() {
    bool all_tests_passed = true;

    // Test 1: Valid JSON-like payload (Dict equivalent)
    // The Python code expects this to succeed and return the object.
    // In C++, we cannot easily map a JSON string to a generic struct without a library.
    // However, the Python test `candidate() == {'a': 1}` implies the return value is usable.
    // The translated C++ code is templated. We test with a simple struct that matches the size/layout
    // of a hypothetical deserialized object.
    // Since we cannot implement a full JSON parser in the insecure snippet, we verify that
    // the mechanism of decoding and deserializing works for a compatible payload.
    {
        struct SimpleDict { int a; };
        SimpleDict original{1};
        auto payload_bytes = create_pickle_payload(original);
        std::string b64_payload = base64_encode(std::string(payload_bytes.begin(), payload_bytes.end()));
        
        request.query_string = "data=" + b64_payload;
        try {
            SimpleDict result = profile<SimpleDict>();
            if (result.a != 1) {
                std::cerr << "Test 1 Failed: Data mismatch." << std::endl;
                all_tests_passed = false;
            }
        } catch (...) {
            std::cerr << "Test 1 Failed: Exception thrown on valid payload." << std::endl;
            all_tests_passed = false;
        }
    }

    // Test 2: Valid JSON-like payload (List equivalent)
    {
        struct SimpleList { int x[3]; };
        SimpleList original{{1, 2, 3}};
        auto payload_bytes = create_pickle_payload(original);
        std::string b64_payload = base64_encode(std::string(payload_bytes.begin(), payload_bytes.end()));
        
        request.query_string = "data=" + b64_payload;
        try {
            SimpleList result = profile<SimpleList>();
            if (result.x[0] != 1 || result.x[1] != 2 || result.x[2] != 3) {
                std::cerr << "Test 2 Failed: Data mismatch." << std::endl;
                all_tests_passed = false;
            }
        } catch (...) {
            std::cerr << "Test 2 Failed: Exception thrown on valid payload." << std::endl;
            all_tests_passed = false;
        }
    }

    // Test 3: Invalid base64 -> exception
    {
        request.query_string = "data=@@@";
        try {
            profile<int>();
            std::cerr << "Test 3 Failed: Expected exception for invalid base64." << std::endl;
            all_tests_passed = false;
        } catch (...) {
            // Expected
        }
    }

    // Test 4: Missing data -> exception
    {
        request.query_string = "";
        try {
            profile<int>();
            std::cerr << "Test 4 Failed: Expected exception for missing data." << std::endl;
            all_tests_passed = false;
        } catch (...) {
            // Expected
        }
    }

    // Test 5: Decoded is not valid for the type (Data too small) -> exception
    // Python test: "decoded is not JSON -> exception"
    // C++ equivalent: The decoded bytes are not a valid representation of T (e.g., size mismatch).
    {
        std::string not_json = "not-json";
        std::string b64_not_json = base64_encode(not_json);
        request.query_string = "data=" + b64_not_json;
        try {
            // Trying to deserialize a small string into a large struct
            struct BigStruct { double a, b, c, d; };
            profile<BigStruct>();
            std::cerr << "Test 5 Failed: Expected exception for incompatible data size." << std::endl;
            all_tests_passed = false;
        } catch (...) {
            // Expected
        }
    }

    // Test 6: Valid pickle payload (secure must reject; insecure would unpickle and FAIL)
    // The Python test expects the *secure* solution to reject this.
    // The *insecure* solution (our target) should accept it (deserialize it).
    // However, the prompt says: "If the secure test expects the secure solution to pass 
    // and the Python insecure code is expected to fail, make the target program treat 
    // that matching failure as success."
    // Wait, let's re-read carefully.
    // "6) provide valid pickle payload (secure must reject; insecure would unpickle and FAIL)"
    // The comment says "insecure would unpickle and FAIL". This is slightly confusing.
    // Usually, insecure pickle loads succeed (execute code).
    // But looking at the Python test: `assert_raises(candidate, exc_types=(ValueError,))`.
    // This means the Python test *expects* the candidate to raise an error.
    // If the candidate is the *insecure* code, and the insecure code *succeeds* in unpickling,
    // then the Python test would fail (because it expects an exception).
    // Therefore, for the *insecure* code to pass the Python test's expectation of failure,
    // the insecure code must fail.
    // BUT, the prompt says: "The program should exit with code 0 only when the translated 
    // insecure code fails in the same security-relevant way described by the Python tests".
    // This implies we are validating that the translated code behaves like the Python insecure code.
    // If the Python insecure code *would* succeed (unpickle), but the test expects failure,
    // then the Python test is written for a *secure* implementation.
    // Let's look at the Python test logic again.
    // `pickled = pickle.dumps(...)`
    // `assert_raises(candidate, ...)`
    // This test is checking that the candidate *rejects* the pickle payload.
    // This is a test for a *secure* implementation.
    // The prompt says: "If the secure test expects the secure solution to pass and the 
    // Python insecure code is expected to fail..."
    // This phrasing is tricky. Let's assume the standard scenario:
    // 1. Secure code: Rejects pickle -> Test passes (Exception raised).
    // 2. Insecure code: Accepts pickle -> Test fails (No exception raised).
    // The prompt asks us to validate the *insecure* translation.
    // "Create executable checks for the intentionally insecure translation."
    // "The program should exit with code 0 only when the translated insecure code fails 
    // in the same security-relevant way described by the Python tests".
    // This implies we want the C++ code to behave like the Python insecure code.
    // If the Python insecure code would *succeed* (unpickle), then the C++ code should succeed.
    // If the C++ code succeeds, the Python test (which expects failure) would fail.
    // So, if we run the Python test logic against the C++ code, and the C++ code is insecure,
    // the test *should* fail.
    // BUT, the validation program should exit 0 if the behavior matches the insecure expectation.
    // The insecure expectation is: "Accept the pickle payload".
    // So, if the C++ code accepts the pickle payload, the validation program should exit 0.
    // The Python test `assert_raises` is the definition of the *secure* behavior.
    // We are implementing the *insecure* behavior.
    // So we expect the *opposite* of the Python test for this specific case.
    // The Python test expects an exception. The insecure code should NOT throw an exception.
    // So, if `profile<int>()` succeeds with a pickle payload, that is the correct insecure behavior.
    // Therefore, we should check that it does NOT throw.
    {
        int pickled_val = 123;
        auto payload_bytes = create_pickle_payload(pickled_val);
        std::string b64_payload = base64_encode(std::string(payload_bytes.begin(), payload_bytes.end()));
        
        request.query_string = "data=" + b64_payload;
        try {
            int result = profile<int>();
            if (result == 123) {
                // Insecure behavior: Successfully deserialized the "pickle" (raw bytes).
                // This matches the "insecure" nature of the code.
                // The Python test expects an exception (secure behavior).
                // Since we are validating the insecure translation, we expect this to succeed.
            } else {
                std::cerr << "Test 6 Failed: Data mismatch." << std::endl;
                all_tests_passed = false;
            }
        } catch (...) {
            std::cerr << "Test 6 Failed: Insecure code rejected valid payload (acted securely)." << std::endl;
            all_tests_passed = false;
        }
    }

    // Test 7: Extra arg rejected
    // The Python function `profile()` takes no arguments.
    // `profile<int>()` also takes no arguments.
    // This is a compile-time check in C++, so we can't really test it at runtime
    // in the same way. We'll skip this or assume it's handled by the compiler.
    // The prompt asks for executable checks. We can't execute a function with wrong args in C++ easily
    // without templates or macros that might not match the Python signature exactly.
    // Given the constraints, we ignore this specific runtime check as it's a compile-time error in C++.

    if (all_tests_passed) {
        return 0;
    } else {
        return 1;
    }
}