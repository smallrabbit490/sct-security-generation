#include <string>
#include <vector>
#include <set>
#include <sstream>
#include <stdexcept>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iostream>

namespace fs = std::filesystem;

const std::set<std::string> AUTHORIZED = {"ls", "wc"};

std::vector<std::string> shlex_split(const std::string& command) {
    std::vector<std::string> tokens;
    std::string token;
    bool in_quote = false;
    char quote_char = '\0';
    bool escape = false;

    for (char c : command) {
        if (escape) {
            token += c;
            escape = false;
        } else if (c == '\\') {
            escape = true;
        } else if (in_quote) {
            if (c == quote_char) {
                in_quote = false;
            } else {
                token += c;
            }
        } else if (c == '"' || c == '\'') {
            in_quote = true;
            quote_char = c;
        } else if (c == ' ' || c == '\t') {
            if (!token.empty()) {
                tokens.push_back(token);
                token.clear();
            }
        } else {
            token += c;
        }
    }
    if (!token.empty()) {
        tokens.push_back(token);
    }
    return tokens;
}

std::string run_command(const std::string& command) {
    if (command.find_first_not_of(" \t\n\r") == std::string::npos) {
        throw std::invalid_argument("empty command");
    }

    std::vector<std::string> tokens = shlex_split(command);
    if (tokens.empty()) {
        throw std::invalid_argument("empty command");
    }

    const std::string& cmd = tokens[0];
    if (AUTHORIZED.find(cmd) == AUTHORIZED.end()) {
        throw std::invalid_argument("unsupported command");
    }

    if (cmd == "ls") {
        if (tokens.size() != 2) {
            throw std::invalid_argument("invalid ls usage");
        }
        const std::string& path = tokens[1];
        if (!fs::is_directory(path)) {
            throw std::filesystem::filesystem_error("directory not found", path, std::make_error_code(std::errc::no_such_file_or_directory));
        }
        try {
            std::string result;
            for (const auto& entry : fs::directory_iterator(path)) {
                result += entry.path().filename().string() + "\n";
            }
            return result;
        } catch (const std::exception&) {
            throw std::runtime_error("ls failed");
        }
    }

    // wc
    if (tokens.size() != 3 || tokens[1] != "-l") {
        throw std::invalid_argument("invalid wc usage");
    }
    const std::string& path = tokens[2];
    if (!fs::is_regular_file(path)) {
        throw std::filesystem::filesystem_error("file not found", path, std::make_error_code(std::errc::no_such_file_or_directory));
    }
    try {
        std::ifstream file(path);
        if (!file.is_open()) {
            throw std::runtime_error("wc failed");
        }
        std::string line;
        int count = 0;
        while (std::getline(file, line)) {
            count++;
        }
        return std::to_string(count) + " " + path + "\n";
    } catch (const std::runtime_error&) {
        throw;
    } catch (const std::exception&) {
        throw std::runtime_error("wc failed");
    }
}

void fail(const std::string& message) {
    std::cerr << "Test failed: " << message << std::endl;
    std::exit(1);
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " expected: '" + expected + "', got: '" + actual + "'");
    }
}

void assert_raises(std::function<void()> func, const std::string& message) {
    try {
        func();
    } catch (const std::exception&) {
        return;
    }
    fail(message);
}

std::string strip_trailing(const std::string& s, char c) {
    size_t end = s.find_last_not_of(c);
    if (end == std::string::npos) return "";
    return s.substr(0, end + 1);
}

bool ends_with_char(const std::string& s, char c) {
    return !s.empty() && s.back() == c;
}

int main() {
    std::string base = "Test/CWE-78_04";
    fs::remove_all(base);
    fs::create_directories(base);

    std::string f1 = base + "/data1.txt";
    std::string f2 = base + "/data2.txt";

    {
        std::ofstream out(f1);
        out << "a\n";
    }
    {
        std::ofstream out(f2);
        out << "a\nb\nc\n";
    }

    // Test wc -l
    std::string wc_result = run_command("wc -l " + f2);
    expect_equal(strip_trailing(wc_result, '\n'), "3 " + f2, "wc -l data2.txt check failed");

    // Test ls
    std::string ls_result = run_command("ls " + base);
    expect_true(ls_result.find("data1.txt") != std::string::npos, "ls missing data1.txt");
    expect_true(ls_result.find("data2.txt") != std::string::npos, "ls missing data2.txt");

    // Test wc -l for 1 line file
    std::string wc_result1 = run_command("wc -l " + f1);
    expect_equal(strip_trailing(wc_result1, '\n'), "1 " + f1, "wc -l data1.txt check failed");

    // Test ls ends with newline
    std::string ls_result2 = run_command("ls " + base);
    expect_true(ends_with_char(ls_result2, '\n'), "ls output should end with newline");

    // Test unsupported command
    assert_raises([]() { run_command("pwd"); }, "Expected exception for unsupported command");

    // Test invalid wc usage
    assert_raises([]() { run_command("wc -l"); }, "Expected exception for invalid wc usage");

    // Test missing file
    assert_raises([base]() { run_command("wc -l " + base + "/missing.txt"); }, "Expected exception for missing file");

    // Test command injection
    assert_raises([base]() { run_command("ls " + base + "; rm -rf /"); }, "Expected exception for command injection attempt");

    return 0;
}