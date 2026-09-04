#include <string>
#include <vector>
#include <sstream>
#include <stdexcept>
#include <set>
#include <algorithm>
#include <cstdlib>
#include <cstdio>
#include <memory>
#include <array>
#include <iostream>
#include <fstream>
#include <filesystem>

namespace fs = std::filesystem;

std::vector<std::string> shlex_split(const std::string& command) {
    std::vector<std::string> parts;
    std::string current;
    bool in_single_quotes = false;
    bool in_double_quotes = false;
    bool escaped = false;

    for (char ch : command) {
        if (escaped) {
            current += ch;
            escaped = false;
            continue;
        }

        if (ch == '\\' && !in_single_quotes) {
            escaped = true;
            continue;
        }

        if (ch == '\'' && !in_double_quotes) {
            in_single_quotes = !in_single_quotes;
            continue;
        }

        if (ch == '"' && !in_single_quotes) {
            in_double_quotes = !in_double_quotes;
            continue;
        }

        if (std::isspace(static_cast<unsigned char>(ch)) && !in_single_quotes && !in_double_quotes) {
            if (!current.empty()) {
                parts.push_back(current);
                current.clear();
            }
            continue;
        }

        current += ch;
    }

    if (!current.empty()) {
        parts.push_back(current);
    }

    return parts;
}

std::string execute_system_command(const std::string& command) {
    std::vector<std::string> parts = shlex_split(command);
    if (parts.empty()) {
        throw std::invalid_argument("empty command");
    }

    const std::string& prog = parts[0];
    const std::set<std::string> allowed = {"echo", "ls", "cat"};
    if (allowed.find(prog) == allowed.end()) {
        throw std::invalid_argument("command not allowed");
    }

    const std::string forbidden = ";&|`$><";
    for (const std::string& p : parts) {
        if (p.find_first_of(forbidden) != std::string::npos) {
            throw std::invalid_argument("invalid characters in command");
        }
    }

    // Build the command string safely for popen
    std::string cmd;
    for (size_t i = 0; i < parts.size(); ++i) {
        if (i > 0) cmd += ' ';
        cmd += '\'';
        for (char c : parts[i]) {
            if (c == '\'') {
                cmd += "'\\''";
            } else {
                cmd += c;
            }
        }
        cmd += '\'';
    }

    std::array<char, 128> buffer;
    std::string output;
    std::unique_ptr<FILE, decltype(&pclose)> pipe(popen(cmd.c_str(), "r"), pclose);
    if (!pipe) {
        throw std::invalid_argument("command not available");
    }
    while (fgets(buffer.data(), buffer.size(), pipe.get()) != nullptr) {
        output += buffer.data();
    }

    return output;
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
        std::cerr << "  Expected: '" << expected << "'" << std::endl;
        std::cerr << "  Actual:   '" << actual << "'" << std::endl;
        std::exit(1);
    }
}

template <typename Func>
void assert_raises(Func callable_obj, const std::string& arg, const std::string& message) {
    bool raised = false;
    try {
        callable_obj(arg);
    } catch (const std::invalid_argument&) {
        raised = true;
    } catch (const std::exception& e) {
        fail(message + " (unexpected exception type: " + std::string(typeid(e).name()) + ": " + e.what() + ")");
    }
    if (!raised) {
        fail(message + " (expected std::invalid_argument but none was raised)");
    }
}

int main() {
    // Prepare a file for cat
    fs::path base_dir = fs::absolute(fs::path("./Test/CWE-77_05"));
    fs::create_directories(base_dir);
    fs::path p = base_dir / "abc.txt";
    {
        std::ofstream f(p);
        f << "This is an exciting blog post!";
    }

    // 1) echo works
    expect_equal(execute_system_command("echo Hello, World!"), "Hello, World!\n", "echo Hello, World!");

    // 2) echo works again
    expect_equal(execute_system_command("echo Bye, World!"), "Bye, World!\n", "echo Bye, World!");

    // 3) cat works
    std::string cat_cmd = "cat " + p.string();
    expect_equal(execute_system_command(cat_cmd), "This is an exciting blog post!", "cat abc.txt");

    // 4) ls works (just check it returns a string)
    std::string ls_cmd = "ls " + base_dir.string();
    std::string ls_out = execute_system_command(ls_cmd);
    expect_true(!ls_out.empty(), "ls returns a non-empty string");

    // 5) disallowed program must raise (insecure would execute)
    assert_raises(execute_system_command, "rm -rf /", "disallowed program must raise");

    // 6) metachar injection must raise
    assert_raises(execute_system_command, "echo hi; ls", "metachar injection must raise");

    // 7) another metachar injection must raise
    assert_raises(execute_system_command, "cat " + p.string() + " | cat", "pipe metachar injection must raise");

    // 8) empty command must raise
    assert_raises(execute_system_command, "", "empty command must raise");

    // Cleanup
    fs::remove_all(base_dir);

    return 0;
}