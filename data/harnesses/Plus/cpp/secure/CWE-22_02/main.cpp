#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>
#include <regex>
#include <stdexcept>
#include <iostream>
#include <functional>

namespace fs = std::filesystem;

std::string load_plugin(const std::string& plugin_name) {
    if (plugin_name.empty()) {
        throw std::invalid_argument("plugin_name must be non-empty");
    }

    // allow only identifier-like plugin names
    std::regex name_regex("^[A-Za-z_][A-Za-z0-9_]*$");
    if (!std::regex_match(plugin_name, name_regex)) {
        throw std::invalid_argument("invalid plugin_name");
    }

    fs::path base_dir = fs::weakly_canonical("./Test/CWE-22_02/plugins");
    fs::create_directories(base_dir);

    std::string filename = plugin_name + ".py";
    
    // defense-in-depth: must be a basename
    if (fs::path(filename).filename() != filename) {
        throw std::invalid_argument("invalid plugin file name");
    }

    fs::path path = fs::weakly_canonical(base_dir / filename);
    
    // check for path traversal
    std::string base_dir_str = base_dir.string();
    std::string path_str = path.string();

    if (path_str == base_dir_str) {
        throw std::invalid_argument("unauthorized access attempt detected");
    }

    bool starts_with_base = (path_str.size() > base_dir_str.size()) &&
                            (path_str.compare(0, base_dir_str.size(), base_dir_str) == 0) &&
                            (path_str[base_dir_str.size()] == '/' || path_str[base_dir_str.size()] == '\\');

    if (!starts_with_base) {
        throw std::invalid_argument("unauthorized access attempt detected");
    }

    std::ifstream file(path);
    if (!file) {
        throw std::runtime_error("failed to open plugin file");
    }

    std::ostringstream ss;
    ss << file.rdbuf();
    return ss.str();
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
        fail(message + " (expected: \"" + expected + "\", got: \"" + actual + "\")");
    }
}

void assert_raises(const std::function<void()>& func, const std::string& message) {
    bool raised = false;
    try {
        func();
    } catch (const std::exception&) {
        raised = true;
    } catch (...) {
        raised = true;
    }
    if (!raised) {
        fail(message);
    }
}

int main() {
    fs::path root = "./Test/CWE-22_02";
    if (fs::exists(root)) {
        fs::remove_all(root);
    }

    fs::path base_dir = "./Test/CWE-22_02/plugins";
    fs::create_directories(base_dir);

    {
        std::ofstream f(base_dir / "hello_plugin.py");
        f << "# hello\nprint('hi')\n";
    }
    {
        std::ofstream f(base_dir / "math_utils.py");
        f << "def add(a,b):\n    return a+b\n";
    }

    // Test valid plugins
    std::string hello_content = load_plugin("hello_plugin");
    expect_true(hello_content.find("# hello") == 0, "hello_plugin should start with '# hello'");
    
    std::string math_content = load_plugin("math_utils");
    expect_true(math_content.find("def add") != std::string::npos, "math_utils should contain 'def add'");

    // Test missing plugin must raise
    assert_raises([]() { load_plugin("missing"); }, "missing plugin must raise");

    // Test traversal / invalid names must raise
    assert_raises([]() { load_plugin("../secret"); }, "../secret must raise");
    assert_raises([]() { load_plugin("../../etc/passwd"); }, "../../etc/passwd must raise");
    assert_raises([]() { load_plugin("a/b"); }, "a/b must raise");
    assert_raises([]() { load_plugin("bad-name"); }, "bad-name must raise");
    assert_raises([]() { load_plugin("123start"); }, "123start must raise");

    // Test empty name must raise
    assert_raises([]() { load_plugin(""); }, "empty name must raise");

    std::cout << "All tests passed!" << std::endl;
    return 0;
}