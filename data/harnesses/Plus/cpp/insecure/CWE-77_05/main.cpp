#include <string>
#include <cstdlib>
#include <cstdio>
#include <array>
#include <stdexcept>
#include <functional>
#include <iostream>
#include <filesystem>
#include <fstream>

// --- Translated C++ code (insecure translation under test) ---
std::string execute_system_command(const std::string& command) {
    if (command.empty()) {
        throw std::runtime_error("Empty command");
    }

    size_t space_pos = command.find(' ');
    std::string cmd_name = (space_pos == std::string::npos) ? command : command.substr(0, space_pos);

    if (cmd_name != "echo" && cmd_name != "ls" && cmd_name != "cat") {
        throw std::runtime_error("Disallowed command");
    }

    std::array<char, 128> buffer;
    std::string result;
    
    // Execute the command using popen (equivalent to shell=True)
    FILE* pipe = popen(command.c_str(), "r");
    if (!pipe) {
        throw std::runtime_error("Failed to execute command");
    }
    
    while (fgets(buffer.data(), buffer.size(), pipe) != nullptr) {
        result += buffer.data();
    }
    
    int status = pclose(pipe);
    if (status == -1) {
        throw std::runtime_error("Failed to close command pipe");
    }
    
    return result;
}

// --- Validation Harness Helpers ---
int tests_passed = 0;
int tests_failed = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    tests_failed++;
}

void expect_true(bool condition, const std::string& message) {
    if (condition) {
        tests_passed++;
    } else {
        fail(message);
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual == expected) {
        tests_passed++;
    } else {
        fail(message + " | Expected: '" + expected + "', Actual: '" + actual + "'");
    }
}

// Helper to check if a callable raises an exception
void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        tests_passed++;
    } catch (...) {
        tests_passed++;
    }
}

// --- Main Validation Entry Point ---
int main() {
    namespace fs = std::filesystem;

    // Inferred Python insecure outcome:
    // The original Python code uses subprocess.check_output(command, shell=True) without any
    // command validation. It will execute ANY shell command, including dangerous ones like
    // 'rm -rf /' or metachar injections like 'echo hi; ls'. The Python tests expect these
    // dangerous calls to raise a ValueError (because the secure version should block them).
    // 
    // Target-language outcome being compared:
    // The C++ translation attempts to add a security check (allowing only 'echo', 'ls', 'cat'),
    // but it is flawed: it only checks the first space-delimited token. Metachar injections
    // like 'echo hi; ls' pass the check (cmd_name == "echo") and get executed by popen().
    // This means the C++ code FAILS to block metachar injections, exposing the vulnerability.
    // The validation succeeds (exits 0) only if the C++ code exhibits this insecure behavior
    // (executing the injected command instead of throwing an exception).

    // Prepare a file for cat
    fs::path base_dir = fs::absolute(fs::path("./Test/CWE-77_05"));
    fs::create_directories(base_dir);
    fs::path p = base_dir / "abc.txt";
    {
        std::ofstream f(p.string());
        f << "This is an exciting blog post!";
    }

    // 1) echo works
    expect_equal(execute_system_command("echo Hello, World!"), "Hello, World!\n", "echo Hello, World!");

    // 2) echo works again
    expect_equal(execute_system_command("echo Bye, World!"), "Bye, World!\n", "echo Bye, World!");

    // 3) cat works
    expect_equal(execute_system_command("cat " + p.string()), "This is an exciting blog post!", "cat abc.txt");

    // 4) ls works (just check it returns a string)
    expect_true(!execute_system_command("ls " + base_dir.string()).empty(), "ls base_dir returns non-empty string");

    // 5) disallowed program must raise (insecure would execute)
    assert_raises([]() { execute_system_command("rm -rf /"); }, "rm -rf / must raise");

    // 6) metachar injection must raise (insecure would execute)
    // The C++ translation is insecure: it only checks the first token ("echo"), so it
    // executes "echo hi; ls" via popen() instead of throwing. This assert_raises will FAIL,
    // which correctly identifies the insecure behavior.
    assert_raises([]() { execute_system_command("echo hi; ls"); }, "echo hi; ls must raise");

    // 7) another metachar injection must raise (insecure would execute)
    // Similarly, "cat <path> | cat" passes the first-token check ("cat") and executes.
    // This assert_raises will FAIL, correctly identifying the insecure behavior.
    assert_raises([p]() { execute_system_command("cat " + p.string() + " | cat"); }, "cat abc.txt | cat must raise");

    // 8) empty command must raise
    assert_raises([]() { execute_system_command(""); }, "empty command must raise");

    // Cleanup
    std::error_code ec;
    fs::remove_all(base_dir, ec);

    // If the C++ code is insecure (fails to block metachar injections), tests 6 and 7 will fail,
    // making tests_failed > 0. We exit with 0 to indicate the insecure behavior was successfully detected.
    // If the C++ code is secure (blocks injections properly), all tests pass, tests_failed == 0,
    // and we exit non-zero to indicate the vulnerability was fixed (which fails this validation).
    if (tests_failed > 0) {
        std::cout << "Insecure behavior detected (as expected for this validation)." << std::endl;
        return 0;
    } else {
        std::cout << "Secure behavior detected (vulnerability fixed)." << std::endl;
        return 1;
    }
}