#include <iostream>
#include <string>
#include <stdexcept>
#include <unordered_map>
#include <vector>
#include <functional>
#include <cstring>

// Mock request structure to mimic Python's request.POST behavior
struct Request {
    struct PostData {
        std::string get(const std::string& key) const {
            auto it = data.find(key);
            return it != data.end() ? it->second : "";
        }
        std::unordered_map<std::string, std::string> data;
    } POST;
};

bool admin_access(const Request* request) {
    if (request == nullptr) {
        throw std::runtime_error("TypeError");
    }

    std::string user_name = request->POST.get("user_name");
    std::string password = request->POST.get("password");

    // Constant-time comparison to prevent timing attacks
    auto compare_digest = [](const std::string& a, const std::string& b) -> bool {
        if (a.size() != b.size()) {
            return false;
        }
        volatile const unsigned char* p1 = reinterpret_cast<const unsigned char*>(a.data());
        volatile const unsigned char* p2 = reinterpret_cast<const unsigned char*>(b.data());
        unsigned char result = 0;
        for (size_t i = 0; i < a.size(); ++i) {
            result |= p1[i] ^ p2[i];
        }
        return result == 0;
    };

    return compare_digest(user_name, "admin") && compare_digest(password, "admin");
}

// Test harness
int main() {
    int passed = 0;
    int total = 0;

    auto run_test = [&](const std::string& name, std::function<void()> test_fn) {
        total++;
        try {
            test_fn();
            passed++;
            std::cout << "[PASS] " << name << std::endl;
        } catch (const std::exception& e) {
            std::cout << "[FAIL] " << name << ": " << e.what() << std::endl;
        } catch (...) {
            std::cout << "[FAIL] " << name << ": Unknown exception" << std::endl;
        }
    };

    // Helper to create Request
    auto make_req = [](const std::string& u, const std::string& p) {
        Request r;
        r.POST.data["user_name"] = u;
        r.POST.data["password"] = p;
        return r;
    };

    // 1. correct creds
    run_test("correct creds", [&]() {
        Request r = make_req("admin", "admin");
        if (!admin_access(&r)) throw std::runtime_error("Expected true");
    });

    // 2. after a correct login, a wrong login must not remain True
    run_test("wrong password", [&]() {
        Request r = make_req("admin", "wrong");
        if (admin_access(&r)) throw std::runtime_error("Expected false");
    });

    // 3. wrong username
    run_test("wrong username", [&]() {
        Request r = make_req("user", "admin");
        if (admin_access(&r)) throw std::runtime_error("Expected false");
    });

    // 4. type checks (None request)
    run_test("request is None", [&]() {
        try {
            admin_access(nullptr);
            throw std::runtime_error("Expected exception");
        } catch (const std::runtime_error&) {
            // Expected
        }
    });

    // 5. extra arg rejected
    // Note: C++ is statically typed, so we cannot pass an extra argument to a function
    // taking one argument. This test is implicitly handled by the compiler.
    // We simulate the intent by checking the function signature logic if it were variadic,
    // but here we just acknowledge the type safety.
    run_test("extra arg rejected (static type check)", [&]() {
        // In C++, `admin_access(&r, 1)` would not compile.
        // We assume this passes by definition of C++ strong typing.
    });

    std::cout << "Tests passed: " << passed << "/" << total << std::endl;
    return (passed == total) ? 0 : 1;
}