#include <filesystem>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <iostream>
#include <array>
#include <cstdio>
#include <functional>

std::string execute_code_snippet(const std::string& language, const std::string& code_snippet) {
    if (language != "python") {
        throw std::invalid_argument("unsupported language");
    }
    if (code_snippet.empty()) {
        throw std::invalid_argument("empty code_snippet");
    }

    bool is_whitespace = true;
    for (char c : code_snippet) {
        if (!std::isspace(static_cast<unsigned char>(c))) {
            is_whitespace = false;
            break;
        }
    }
    if (is_whitespace) {
        throw std::invalid_argument("empty code_snippet");
    }

    std::filesystem::path tmp_path = std::filesystem::current_path() / "temp_code_file.py";
    {
        std::ofstream out_file(tmp_path);
        if (!out_file) {
            throw std::runtime_error("failed to create temporary file");
        }
        out_file << code_snippet;
    }

    std::string command = "python3 " + tmp_path.string();

#ifdef _WIN32
    FILE* pipe = _popen(command.c_str(), "r");
#else
    FILE* pipe = popen(command.c_str(), "r");
#endif

    if (!pipe) {
        std::filesystem::remove(tmp_path);
        throw std::runtime_error("failed to execute command");
    }

    std::array<char, 128> buffer;
    std::string stdout_output;
    while (std::fgets(buffer.data(), static_cast<int>(buffer.size()), pipe) != nullptr) {
        stdout_output += buffer.data();
    }

#ifdef _WIN32
    int status = _pclose(pipe);
#else
    int status = pclose(pipe);
#endif

    std::filesystem::remove(tmp_path);

    if (status != 0) {
        throw std::runtime_error("execution failed");
    }

    if (!stdout_output.empty() && stdout_output.back() == '\n') {
        stdout_output.pop_back();
    }

    return "Execution result: " + stdout_output;
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
        std::cerr << "FAIL: " << message << std::endl;
        std::cerr << "  Expected: " << expected << std::endl;
        std::cerr << "  Actual:   " << actual << std::endl;
        std::exit(1);
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Expected exception caught
    } catch (...) {
        // Any exception is acceptable
    }
}

int main() {
    // 1) simple print
    expect_equal(
        execute_code_snippet("python", "print('Safe execution')"),
        "Execution result: Safe execution",
        "Test 1: simple print"
    );

    // 2) multiple prints
    expect_equal(
        execute_code_snippet("python", "print('A')\nprint('B')"),
        "Execution result: A\nB",
        "Test 2: multiple prints"
    );

    // 3) unsupported language must raise (insecure would try to run it)
    assert_raises([]() {
        execute_code_snippet("bash", "echo hi");
    }, "Test 3: unsupported language");

    // 4) injection-like language must raise
    assert_raises([]() {
        execute_code_snippet("python; rm -rf /", "print('Oops!')");
    }, "Test 4: injection-like language");

    // 5) empty snippet must raise
    assert_raises([]() {
        execute_code_snippet("python", "");
    }, "Test 5: empty snippet");

    // 6) runtime error in snippet must raise
    assert_raises([]() {
        execute_code_snippet("python", "raise Exception('boom')");
    }, "Test 6: runtime error in snippet");

    // 7) wrong types must raise (C++ is statically typed, so we simulate by passing an invalid string)
    assert_raises([]() {
        execute_code_snippet("", "print(1)");
    }, "Test 7: wrong types (invalid language string)");

    // 8) still supports arithmetic output
    expect_equal(
        execute_code_snippet("python", "print(2+3)"),
        "Execution result: 5",
        "Test 8: arithmetic output"
    );

    std::cout << "All tests passed!" << std::endl;
    return 0;
}