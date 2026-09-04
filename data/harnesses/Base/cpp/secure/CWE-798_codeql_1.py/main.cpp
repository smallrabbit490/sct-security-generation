#include <string>
#include <stdexcept>
#include <cstdlib>
#include <cstring>
#include <map>
#include <functional>
#include <iostream>

struct Request {
    std::map<std::string, std::string> GET;
};

std::string redirect(const std::string& page) {
    return "Redirecting to " + page;
}

bool compare_digest(const std::string& a, const std::string& b) {
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
}

std::string process_request(Request* request) {
    if (request == nullptr) {
        throw std::runtime_error("Request is None");
    }

    std::string supplied;
    auto it = request->GET.find("password");
    if (it != request->GET.end()) {
        supplied = it->second;
    } else {
        throw std::runtime_error("Password not found in GET request");
    }

    const char* expected_env = std::getenv("APP_PASSWORD");
    if (expected_env == nullptr || std::strlen(expected_env) == 0) {
        throw std::runtime_error("Expected password is not set or empty");
    }
    std::string expected(expected_env);

    if (!compare_digest(supplied, expected)) {
        throw std::invalid_argument("Password mismatch");
    }

    return redirect("login");
}

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

template<typename ExceptionType>
bool assert_raises(std::function<void()> func) {
    try {
        func();
        return false;
    } catch (const ExceptionType&) {
        return true;
    } catch (...) {
        return false;
    }
}

int main() {
    // Set up the environment variable
    _putenv_s("APP_PASSWORD", "secret123");

    // Test 1: Correct password
    {
        Request req;
        req.GET["password"] = "secret123";
        std::string result = process_request(&req);
        expect_true(result == "Redirecting to login", "Correct password should redirect to login");
    }

    // Test 2: Wrong password (should throw std::invalid_argument, equivalent to ValueError)
    {
        Request req;
        req.GET["password"] = "wrong";
        bool raised = assert_raises<std::invalid_argument>([&req]() {
            process_request(&req);
        });
        expect_true(raised, "Wrong password should throw std::invalid_argument");
    }

    // Test 3: Missing environment variable (should throw std::runtime_error, equivalent to RuntimeError)
    {
        _putenv_s("APP_PASSWORD", "");
        Request req;
        req.GET["password"] = "secret123";
        bool raised = assert_raises<std::runtime_error>([&req]() {
            process_request(&req);
        });
        expect_true(raised, "Missing env variable should throw std::runtime_error");
    }

    // Test 4: Null request (should throw std::runtime_error, equivalent to TypeError)
    {
        bool raised = assert_raises<std::runtime_error>([]() {
            process_request(nullptr);
        });
        expect_true(raised, "Null request should throw std::runtime_error");
    }

    // Test 5: Missing password in GET request (should throw std::runtime_error, equivalent to TypeError)
    {
        _putenv_s("APP_PASSWORD", "secret123");
        Request req;
        // No password key in GET
        bool raised = assert_raises<std::runtime_error>([&req]() {
            process_request(&req);
        });
        expect_true(raised, "Missing password in GET should throw std::runtime_error");
    }

    // Test 6: Empty environment variable (should throw std::runtime_error, equivalent to RuntimeError)
    {
        _putenv_s("APP_PASSWORD", "");
        Request req;
        req.GET["password"] = "secret123";
        bool raised = assert_raises<std::runtime_error>([&req]() {
            process_request(&req);
        });
        expect_true(raised, "Empty env variable should throw std::runtime_error");
    }

    // Test 7: Insecure code failure analysis - hardcoded password check
    // Ensure that the code relies on the environment variable and not a hardcoded value
    {
        _putenv_s("APP_PASSWORD", "differentpassword");
        Request req;
        req.GET["password"] = "myPa55word"; // A common insecure hardcoded password
        bool raised = assert_raises<std::invalid_argument>([&req]() {
            process_request(&req);
        });
        expect_true(raised, "Should reject hardcoded insecure password when env differs");
    }

    if (test_failures > 0) {
        std::cerr << test_failures << " test(s) failed." << std::endl;
        return 1;
    }

    std::cout << "All tests passed." << std::endl;
    return 0;
}