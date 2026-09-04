#include <string>
#include <fstream>
#include <sstream>
#include <cstdlib>
#include <cstdio>
#include <stdexcept>
#include <vector>
#include <filesystem>
#include <random>
#include <chrono>
#include <functional>
#include <iostream>

namespace fs = std::filesystem;

std::string execute_script(const std::string& script_content) {
    const std::vector<std::string> forbidden = {
        "__import__", "import os", "import subprocess", "open(", "exec(", "eval("
    };

    for (const auto& tok : forbidden) {
        if (script_content.find(tok) != std::string::npos) {
            throw std::invalid_argument("unsupported script content");
        }
    }

    // Generate a unique temporary file name using random numbers
    auto now = std::chrono::high_resolution_clock::now();
    auto seed = now.time_since_epoch().count();
    std::mt19937 gen(static_cast<unsigned>(seed));
    std::uniform_int_distribution<unsigned int> dist(0, 999999);

    fs::path temp_path = fs::temp_directory_path() / ("script_" + std::to_string(dist(gen)) + ".py");
    std::string tmp_name_str = temp_path.string();

    {
        std::ofstream out_file(tmp_name_str, std::ios::out | std::ios::binary);
        if (!out_file) {
            throw std::runtime_error("failed to open temporary file for writing");
        }
        out_file << script_content;
        out_file.close();
        if (out_file.fail()) {
            fs::remove(tmp_name_str);
            throw std::runtime_error("failed to write to temporary file");
        }
    }

    std::string command = "python \"" + tmp_name_str + "\" 2>&1";

    FILE* pipe = popen(command.c_str(), "r");
    if (!pipe) {
        fs::remove(tmp_name_str);
        throw std::runtime_error("failed to run script");
    }

    std::string result;
    char buffer[128];
    while (fgets(buffer, sizeof(buffer), pipe) != nullptr) {
        result += buffer;
    }

    int exit_code = pclose(pipe);

    try {
        fs::remove(tmp_name_str);
    } catch (...) {
        // Swallow exceptions during cleanup
    }

    if (exit_code != 0) {
        throw std::runtime_error("script failed");
    }

    return "Execution Result: " + result;
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
        fail(message + " | Expected: '" + expected + "', Actual: '" + actual + "'");
    }
}

template <typename Func>
void assert_raises(Func callable_obj, const std::string& exc_type_name) {
    try {
        callable_obj();
    } catch (const std::invalid_argument&) {
        if (exc_type_name.find("invalid_argument") == std::string::npos) {
            fail("Unexpected exception type: caught std::invalid_argument but expected " + exc_type_name);
        }
        return;
    } catch (const std::runtime_error&) {
        if (exc_type_name.find("runtime_error") == std::string::npos) {
            fail("Unexpected exception type: caught std::runtime_error but expected " + exc_type_name);
        }
        return;
    } catch (const std::exception& e) {
        // Fallback for other standard exceptions
        return;
    } catch (...) {
        fail("Unexpected unknown exception type");
    }
    fail("Expected an exception but none was raised (expected " + exc_type_name + ")");
}

int main() {
    // Test 1: Safe script execution
    std::string script1 = "print('Safe script execution')";
    std::string result1 = execute_script(script1);
    expect_equal(result1, "Execution Result: Safe script execution\n", "Test 1 failed");

    // Test 2: Expression evaluation
    std::string script2 = "print(1+2)";
    std::string result2 = execute_script(script2);
    expect_equal(result2, "Execution Result: 3\n", "Test 2 failed");

    // Test 3: Forbidden tokens must raise std::invalid_argument
    assert_raises([]() { execute_script("__import__('os').system('echo Malicious code')"); }, "invalid_argument");
    assert_raises([]() { execute_script("import os\nprint('x')"); }, "invalid_argument");
    assert_raises([]() { execute_script("print(open('x','w'))"); }, "invalid_argument");
    assert_raises([]() { execute_script("import subprocess"); }, "invalid_argument");
    assert_raises([]() { execute_script("exec('print(1)')"); }, "invalid_argument");
    assert_raises([]() { execute_script("eval('1+2')"); }, "invalid_argument");

    // Test 4: Script that fails at runtime must raise std::runtime_error
    assert_raises([]() { execute_script("raise Exception('fail')"); }, "runtime_error");

    return 0;
}