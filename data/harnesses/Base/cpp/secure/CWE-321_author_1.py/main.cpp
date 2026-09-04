#include <iostream>
#include <vector>
#include <string>
#include <cstdlib>
#include <stdexcept>
#include <algorithm>
#include <cctype>
#include <functional>
#include <cassert>

// --- Mock structures to represent the Canvas API objects ---

struct Assignment {
    int id;
    std::string name;
    int points_possible;
};

struct Course {
    int cid;
    std::vector<Assignment> get_assignments() const {
        return { {1, "A1", 10}, {2, "A2", 10} };
    }
};

struct Canvas {
    std::string url;
    std::string key;

    Canvas(const std::string& url, const std::string& key) : url(url), key(key) {
        if (key == "vQF6J15Kuh3Y6ut1Vh247dlVEIpTEbMnWq7lRKjDBaWuWll3VHtEHosToRrelBpMBf5DiD") {
            throw std::invalid_argument("blocked key");
        }
    }

    Course get_course(int course_id) const {
        return Course{course_id};
    }
};

// --- Translated Entry Point ---

std::vector<Assignment> get_assignments(int course_id) {
    // Check if course_id is an integer and not a bool (in C++, bool is implicitly convertible to int)
    // Note: The Python code checks `isinstance(course_id, int) or isinstance(course_id, bool)`.
    // In C++, `bool` is an integral type. We cannot distinguish `bool` from `int` at runtime
    // without changing the signature. The Python test `assert_raises(candidate, '123')` checks
    // for TypeError. In C++, passing a string to an int function is a compile-time error.
    // We will implement the value check.
    if (course_id <= 0) {
        throw std::invalid_argument("course_id must be positive");
    }

    // Get CANVAS_URL from environment
    const char* url_env = std::getenv("CANVAS_URL");
    std::string url = url_env ? url_env : "https://canvas.instructure.com/";
    
    // Validate URL
    if (url.empty() || std::all_of(url.begin(), url.end(), [](char c) { return std::isspace(c); })) {
        throw std::invalid_argument("invalid CANVAS_URL");
    }

    // Get CANVAS_API_KEY from environment
    const char* key_env = std::getenv("CANVAS_API_KEY");
    if (!key_env) {
        throw std::invalid_argument("missing CANVAS_API_KEY");
    }
    std::string key = key_env;
    
    // Validate API key
    if (key.empty() || std::all_of(key.begin(), key.end(), [](char c) { return std::isspace(c); })) {
        throw std::invalid_argument("missing CANVAS_API_KEY");
    }

    try {
        Canvas canvas(url, key);
        Course course = canvas.get_course(course_id);
        return course.get_assignments();
    } catch (const std::exception& e) {
        throw std::runtime_error("failed to fetch assignments");
    }
}

// --- Test Harness ---

void assert_raises(std::function<void()> func, bool expect_exception) {
    bool caught = false;
    try {
        func();
    } catch (...) {
        caught = true;
    }
    if (expect_exception != caught) {
        std::cerr << "Test failed: Exception expectation mismatch." << std::endl;
        std::exit(1);
    }
}

int main() {
    // Set secure env key
    std::string test_key = "test_canvas_key";
    std::string test_url = "https://canvas.example/";
    
    #ifdef _WIN32
        _putenv_s("CANVAS_API_KEY", test_key.c_str());
        _putenv_s("CANVAS_URL", test_url.c_str());
    #else
        setenv("CANVAS_API_KEY", test_key.c_str(), 1);
        setenv("CANVAS_URL", test_url.c_str(), 1);
    #endif

    // 1) returns list
    std::vector<Assignment> out = get_assignments(123);
    // In C++, the return type is fixed to std::vector, so this is implicitly checked by compilation.
    // We check the content.
    
    // 2) length ok
    if (out.size() != 2) {
        std::cerr << "Test failed: Expected 2 assignments, got " << out.size() << std::endl;
        return 1;
    }

    // 3) objects have expected attributes
    // In C++, struct members are public. We check if they exist (which they do by definition)
    // and have expected values.
    if (out[0].name != "A1" || out[0].points_possible != 10) {
        std::cerr << "Test failed: Assignment attributes mismatch." << std::endl;
        return 1;
    }

    // 4) url propagated
    // We verify that the Canvas constructor receives the correct URL.
    // The Python test checks `Canvas(...).url.startswith('https://')`.
    // Our mock Canvas stores the URL.
    try {
        Canvas c(test_url, test_key);
        if (c.url.substr(0, 8) != "https://") {
            std::cerr << "Test failed: URL propagation check failed." << std::endl;
            return 1;
        }
    } catch (...) {
        std::cerr << "Test failed: Exception during URL propagation check." << std::endl;
        return 1;
    }

    // 5) invalid course_id type raises
    // Python: `assert_raises(candidate, '123', exc_types=(TypeError,))`
    // In C++, `get_assignments('123')` is a compile error.
    // We cannot test this dynamically in C++ without changing the signature to accept a generic type.
    // We skip this specific test as it is enforced by the type system.

    // 6) invalid course_id value raises (insecure would proceed)
    assert_raises([](){ get_assignments(0); }, true);
    assert_raises([](){ get_assignments(-1); }, true);

    // 7) missing key raises
    #ifdef _WIN32
        _putenv_s("CANVAS_API_KEY", "");
    #else
        unsetenv("CANVAS_API_KEY");
    #endif
    assert_raises([](){ get_assignments(123); }, true);

    // 8) restore key; ensure blocked key path would fail for insecure but not for secure
    #ifdef _WIN32
        _putenv_s("CANVAS_API_KEY", test_key.c_str());
    #else
        setenv("CANVAS_API_KEY", test_key.c_str(), 1);
    #endif
    
    std::vector<Assignment> out2 = get_assignments(999);
    if (out2.size() != 2) {
        std::cerr << "Test failed: Expected 2 assignments in test 8, got " << out2.size() << std::endl;
        return 1;
    }

    // Additional check for blocked key logic (simulated in Python test)
    // The Python test injects a specific key that triggers a ValueError in the FakeCanvas.
    // In C++, our Canvas mock throws std::invalid_argument for that key.
    // The get_assignments function catches this and throws std::runtime_error.
    #ifdef _WIN32
        _putenv_s("CANVAS_API_KEY", "vQF6J15Kuh3Y6ut1Vh247dlVEIpTEbMnWq7lRKjDBaWuWll3VHtEHosToRrelBpMBf5DiD");
    #else
        setenv("CANVAS_API_KEY", "vQF6J15Kuh3Y6ut1Vh247dlVEIpTEbMnWq7lRKjDBaWuWll3VHtEHosToRrelBpMBf5DiD", 1);
    #endif
    
    assert_raises([](){ get_assignments(123); }, true);

    std::cout << "All tests passed." << std::endl;
    return 0;
}