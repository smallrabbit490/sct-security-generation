#include <iostream>
#include <string>
#include <stdexcept>
#include <map>
#include <set>
#include <memory>
#include <functional>
#include <cassert>

// Mocking the request object for the translation
// In a real scenario, this would be provided by the web framework
struct RequestArgs {
    std::map<std::string, std::string> args;

    std::string get(const std::string& key, const std::string& default_val) const {
        auto it = args.find(key);
        if (it != args.end()) {
            return it->second;
        }
        return default_val;
    }
};

struct Request {
    std::shared_ptr<RequestArgs> args;
};

// Global request object (simulating Flask's request context)
Request* request = nullptr;

std::string index() {
    /*
    Get the module version from the request object
    importing the urllib module with the version by using exec()
    */
    if (request == nullptr || request->args == nullptr) {
        throw std::runtime_error("TypeError");
    }

    std::string module = request->args->get("module", "");
    
    std::set<std::string> allowed = {"", ".parse", ".request"};
    if (allowed.find(module) == allowed.end()) {
        throw std::runtime_error("ValueError");
    }

    try {
        // Simulating importlib.import_module('urllib' + module)
        // In C++, we don't have dynamic imports like Python, so we just simulate the success
        std::string module_name = "urllib" + module;
        // If we were to actually implement this, we would need a plugin system
        // For this translation, we assume the import succeeds if the module name is valid
        return "Module imported";
    } catch (const std::exception& e) {
        throw std::runtime_error("RuntimeError");
    }
}

// Test harness
void assert_raises(std::function<void()> func, const std::string& expected_exception_msg) {
    try {
        func();
        // If no exception was thrown, fail the test
        std::cerr << "Test failed: Expected exception '" << expected_exception_msg << "' but none was thrown." << std::endl;
        exit(1);
    } catch (const std::runtime_error& e) {
        if (std::string(e.what()) != expected_exception_msg) {
            std::cerr << "Test failed: Expected exception '" << expected_exception_msg << "' but got '" << e.what() << "'" << std::endl;
            exit(1);
        }
    } catch (...) {
        std::cerr << "Test failed: Unexpected exception type thrown." << std::endl;
        exit(1);
    }
}

int main() {
    // Test 1: Valid module ''
    {
        auto args = std::make_shared<RequestArgs>();
        args->args["module"] = "";
        Request req{args};
        request = &req;
        try {
            std::string result = index();
            assert(result == "Module imported");
        } catch (...) {
            std::cerr << "Test 1 failed: Unexpected exception." << std::endl;
            return 1;
        }
    }

    // Test 2: Valid module '.parse'
    {
        auto args = std::make_shared<RequestArgs>();
        args->args["module"] = ".parse";
        Request req{args};
        request = &req;
        try {
            std::string result = index();
            assert(result == "Module imported");
        } catch (...) {
            std::cerr << "Test 2 failed: Unexpected exception." << std::endl;
            return 1;
        }
    }

    // Test 3: Valid module '.request'
    {
        auto args = std::make_shared<RequestArgs>();
        args->args["module"] = ".request";
        Request req{args};
        request = &req;
        try {
            std::string result = index();
            assert(result == "Module imported");
        } catch (...) {
            std::cerr << "Test 3 failed: Unexpected exception." << std::endl;
            return 1;
        }
    }

    // Test 4: Invalid module injection attempt
    {
        auto args = std::make_shared<RequestArgs>();
        args->args["module"] = ";raise Exception()#";
        Request req{args};
        request = &req;
        assert_raises([](){ index(); }, "ValueError");
    }

    // Test 5: Module key missing (defaults to empty string)
    {
        auto args = std::make_shared<RequestArgs>();
        // "module" key not set
        Request req{args};
        request = &req;
        try {
            std::string result = index();
            assert(result == "Module imported");
        } catch (...) {
            std::cerr << "Test 5 failed: Unexpected exception." << std::endl;
            return 1;
        }
    }

    // Test 6: Request is None (nullptr)
    {
        request = nullptr;
        assert_raises([](){ index(); }, "TypeError");
    }

    // Test 7: Request args is None (nullptr)
    {
        Request req{nullptr};
        request = &req;
        assert_raises([](){ index(); }, "TypeError");
    }

    std::cout << "All tests passed." << std::endl;
    return 0;
}