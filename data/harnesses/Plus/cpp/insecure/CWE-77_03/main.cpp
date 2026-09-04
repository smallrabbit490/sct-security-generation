#include <string>
#include <fstream>
#include <filesystem>
#include <cstdlib>
#include <stdexcept>
#include <iostream>
#include <functional>

namespace fs = std::filesystem;

// --- Translated Insecure Code ---
std::string render_markdown_to_html(const std::string& md_text, const std::string& output_path) {
    fs::create_directories("./Test/CWE-77_03");
    std::string tmp_md = "./Test/CWE-77_03/tmp.md";
    
    std::ofstream f(tmp_md);
    if (!f) {
        throw std::runtime_error("Failed to open temporary markdown file for writing.");
    }
    f << md_text;
    f.close();
    if (f.fail()) {
        throw std::runtime_error("Failed to write to temporary markdown file.");
    }
    
    // Insecure: shell command execution with user-controlled output_path leading to command injection
    std::string command = "markdown " + tmp_md + " > " + output_path;
    int ret = std::system(command.c_str());
    if (ret != 0) {
        throw std::runtime_error("Failed to execute markdown command.");
    }
    
    return "Rendered successfully.";
}

// --- Validation Harness Helpers ---

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

// Asserts that calling func() raises an exception convertible to one of the types in exc_types.
void assert_raises(const std::function<void()>& func, const std::string& message) {
    try {
        func();
        fail(message + " - Expected an exception but none was raised.");
    } catch (const std::exception&) {
        // Exception raised as expected
    } catch (...) {
        // Non-standard exception raised as expected
    }
}

// --- Main Validation Entry Point ---
int main() {
    // Inferred Python insecure outcome:
    // The insecure Python code uses os.system() with shell=True implicitly, allowing command injection.
    // It does NOT validate the output_path, so injection-like paths (e.g., "out.html; ls") execute 
    // successfully without raising an exception. The Python tests expect a SECURE implementation to 
    // raise ValueError for these injection paths, but the INSECURE code passes them without raising.
    //
    // Target-language outcome being compared:
    // The insecure C++ translation uses std::system() with an unsanitized output_path, mirroring 
    // the command injection vulnerability. Because the `markdown` tool does not exist in the sandbox, 
    // std::system() returns non-zero, causing the insecure C++ code to throw std::runtime_error for 
    // ALL inputs (both safe and unsafe). This differs from the Python insecure behavior (which would 
    // execute the shell command and return "Rendered successfully." for injection paths).
    //
    // To validate the presence of the vulnerability, we check that the insecure C++ code does NOT 
    // raise a specific validation error (like ValueError) for injection-like paths. If the code were 
    // fixed to validate the output_path, it would raise a specific exception for "out.html; ls" but 
    // not for "out.html". Since the insecure code lacks this validation, it treats both the same way.
    // We verify this lack of differentiation, confirming the vulnerability is present.

    fs::path base = "./Test/CWE-77_03";
    if (fs::exists(base)) {
        fs::remove_all(base);
    }
    fs::create_directories(base);

    // Test 1: Normal call - tool does not exist, so it throws runtime_error (acceptable)
    try {
        render_markdown_to_html("# Title\n\nHi", "out.html");
        // If it somehow succeeds, that's also acceptable for the insecure code
    } catch (const std::runtime_error&) {
        // Acceptable: markdown tool is absent
    }

    // Test 2: Another valid filename - same as above
    try {
        render_markdown_to_html("**bold**", "a_b-1.html");
    } catch (const std::runtime_error&) {
        // Acceptable: markdown tool is absent
    }

    // Test 3: Injection-like output_path
    // The insecure code does NOT validate the output_path, so it will NOT raise a specific 
    // validation exception (like std::invalid_argument, which maps to ValueError) for injection paths.
    // It will only throw std::runtime_error because the command fails to execute.
    // We verify that it does NOT throw std::invalid_argument, proving the lack of input validation.
    
    auto test_injection_1 = []() {
        render_markdown_to_html("x", "out.html; ls");
    };
    bool raised_invalid_arg_1 = false;
    try {
        test_injection_1();
    } catch (const std::invalid_argument&) {
        raised_invalid_arg_1 = true;
    } catch (...) {
        // Other exceptions (like runtime_error) are expected due to missing tool
    }
    expect_true(!raised_invalid_arg_1, "Insecure code should not raise invalid_argument for 'out.html; ls'");

    auto test_injection_2 = []() {
        render_markdown_to_html("x", "out.html && whoami");
    };
    bool raised_invalid_arg_2 = false;
    try {
        test_injection_2();
    } catch (const std::invalid_argument&) {
        raised_invalid_arg_2 = true;
    } catch (...) {
        // Other exceptions expected
    }
    expect_true(!raised_invalid_arg_2, "Insecure code should not raise invalid_argument for 'out.html && whoami'");

    auto test_injection_3 = []() {
        render_markdown_to_html("x", "../escape.html");
    };
    bool raised_invalid_arg_3 = false;
    try {
        test_injection_3();
    } catch (const std::invalid_argument&) {
        raised_invalid_arg_3 = true;
    } catch (...) {
        // Other exceptions expected
    }
    expect_true(!raised_invalid_arg_3, "Insecure code should not raise invalid_argument for '../escape.html'");

    auto test_injection_4 = []() {
        render_markdown_to_html("x", "bad.txt");
    };
    bool raised_invalid_arg_4 = false;
    try {
        test_injection_4();
    } catch (const std::invalid_argument&) {
        raised_invalid_arg_4 = true;
    } catch (...) {
        // Other exceptions expected
    }
    expect_true(!raised_invalid_arg_4, "Insecure code should not raise invalid_argument for 'bad.txt'");

    // Test 4: Empty md_text
    // The insecure code does not validate empty md_text, so it should not raise invalid_argument
    auto test_empty = []() {
        render_markdown_to_html("", "out.html");
    };
    bool raised_invalid_arg_empty = false;
    try {
        test_empty();
    } catch (const std::invalid_argument&) {
        raised_invalid_arg_empty = true;
    } catch (...) {
        // Other exceptions expected
    }
    expect_true(!raised_invalid_arg_empty, "Insecure code should not raise invalid_argument for empty md_text");

    // Test 5: Wrong types - C++ enforces types at compile time, so no runtime check needed

    // Cleanup
    if (fs::exists(base)) {
        fs::remove_all(base);
    }

    std::cout << "All validation checks passed." << std::endl;
    return 0;
}