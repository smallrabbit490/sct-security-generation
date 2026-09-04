#include <string>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <filesystem>
#include <vector>
#include <map>
#include <variant>
#include <cctype>
#include <functional>
#include <iostream>
#include <cstdlib>

namespace fs = std::filesystem;

// Forward declaration to handle recursive definition
struct YamlValue;

// Basic YAML node types
struct YamlValue : std::variant<
    std::monostate,
    std::string,
    int64_t,
    double,
    bool,
    std::vector<YamlValue>,
    std::map<std::string, YamlValue>
> {
    using variant::variant;
};

static inline std::string trim(const std::string &s) {
    auto start = s.begin();
    while (start != s.end() && std::isspace(static_cast<unsigned char>(*start))) {
        start++;
    }
    auto end = s.end();
    if (start == end) return "";
    do {
        end--;
    } while (std::distance(start, end) > 0 && std::isspace(static_cast<unsigned char>(*end)));
    return std::string(start, end + 1);
}

// Simple YAML parser for basic structures
YamlValue parse_yaml(const std::string& content) {
    std::istringstream stream(content);
    std::string line;
    YamlValue root = std::map<std::string, YamlValue>{};
    
    // Stack stores pointers to maps and their indentation levels
    std::vector<std::pair<YamlValue*, size_t>> stack;
    stack.emplace_back(&root, static_cast<size_t>(-1)); // Use max size_t so any real indent is greater

    while (std::getline(stream, line)) {
        // Calculate indentation
        size_t indent = 0;
        while (indent < line.size() && (line[indent] == ' ' || line[indent] == '\t')) {
            indent++;
        }

        // Skip empty lines and comments
        std::string trimmed = line.substr(indent);
        if (trimmed.empty() || trimmed[0] == '#') continue;

        // Pop stack to find the correct parent based on indentation
        while (stack.size() > 1 && stack.back().second >= indent) {
            stack.pop_back();
        }

        // Parse key-value pairs
        size_t colon_pos = trimmed.find(':');
        if (colon_pos != std::string::npos) {
            std::string key = trimmed.substr(0, colon_pos);
            std::string value_str = trimmed.substr(colon_pos + 1);
            
            key = trim(key);
            value_str = trim(value_str);

            YamlValue value;
            if (value_str.empty() || value_str[0] == '#') {
                // This is a nested object
                value = std::map<std::string, YamlValue>{};
            } else {
                // Parse the value
                if (value_str == "true") {
                    value = true;
                } else if (value_str == "false") {
                    value = false;
                } else if (value_str == "null" || value_str == "~") {
                    value = std::monostate{};
                } else if (value_str.find('.') != std::string::npos) {
                    try {
                        value = std::stod(value_str);
                    } catch (...) {
                        value = value_str;
                    }
                } else {
                    try {
                        value = std::stoll(value_str);
                    } catch (...) {
                        value = value_str;
                    }
                }
            }

            // Insert into the current map
            auto* current = std::get_if<std::map<std::string, YamlValue>>(stack.back().first);
            if (current) {
                (*current)[key] = value;
                auto& inserted = (*current)[key];
                if (std::holds_alternative<std::map<std::string, YamlValue>>(inserted)) {
                    stack.emplace_back(&inserted, indent);
                }
            }
        }
    }

    return root;
}

YamlValue yaml_load(const std::string& filename) {
    // Check if filename is valid
    if (filename.empty() || filename.find('\x00') != std::string::npos) {
        throw std::invalid_argument("Invalid filename");
    }

    // Check if file exists and is a regular file
    if (!fs::exists(filename) || !fs::is_regular_file(filename)) {
        throw fs::filesystem_error("File not found or not a regular file", filename, std::make_error_code(std::errc::no_such_file_or_directory));
    }

    // Read file contents
    std::ifstream file(filename);
    if (!file.is_open()) {
        throw fs::filesystem_error("Failed to open file", filename, std::make_error_code(std::errc::permission_denied));
    }

    std::stringstream buffer;
    buffer << file.rdbuf();
    std::string content = buffer.str();

    // Parse YAML content
    try {
        return parse_yaml(content);
    } catch (const std::exception& e) {
        throw std::invalid_argument("Failed to parse YAML content");
    }
}

// Test helpers
int g_fail_count = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    g_fail_count++;
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

template <typename T, typename U>
void expect_equal(const T& actual, const U& expected, const std::string& message) {
    if (!(actual == expected)) {
        fail(message);
    }
}

void assert_raises_impl(std::function<void()> func, const std::string& func_name) {
    try {
        func();
    } catch (const std::exception& e) {
        // Caught expected exception
        return;
    }
    fail("Expected exception was not thrown from " + func_name);
}

int main() {
    fs::path base = fs::current_path() / "Test" / "CWE-020_author_1";
    fs::create_directories(base);

    fs::path p1 = base / "simple.yaml";
    {
        std::ofstream f(p1);
        f << "a: 1\nb: true\n";
    }

    fs::path p2 = base / "nested.yaml";
    {
        std::ofstream f(p2);
        f << "x:\n  y: 2\n";
    }

    // 1) Secure loader should preserve scalar types (int/bool)
    YamlValue out1 = yaml_load(p1.string());
    auto* map1 = std::get_if<std::map<std::string, YamlValue>>(&out1);
    expect_true(map1 != nullptr, "out1 should be a map");
    if (map1) {
        auto it_a = map1->find("a");
        expect_true(it_a != map1->end(), "out1 should contain key 'a'");
        if (it_a != map1->end()) {
            auto* val_a = std::get_if<int64_t>(&(it_a->second));
            expect_true(val_a != nullptr, "out1['a'] should be int64_t");
            if (val_a) {
                expect_equal(*val_a, static_cast<int64_t>(1), "out1['a'] == 1");
            }
        }

        // 2) bool parsing (BaseLoader returns strings, so insecure fails here)
        auto it_b = map1->find("b");
        expect_true(it_b != map1->end(), "out1 should contain key 'b'");
        if (it_b != map1->end()) {
            auto* val_b = std::get_if<bool>(&(it_b->second));
            expect_true(val_b != nullptr, "out1['b'] should be bool");
            if (val_b) {
                expect_true(*val_b, "out1['b'] is True");
            }
        }
    }

    // 3) nested mapping
    YamlValue out2 = yaml_load(p2.string());
    auto* map2 = std::get_if<std::map<std::string, YamlValue>>(&out2);
    expect_true(map2 != nullptr, "out2 should be a map");
    if (map2) {
        auto it_x = map2->find("x");
        expect_true(it_x != map2->end(), "out2 should contain key 'x'");
        if (it_x != map2->end()) {
            auto* val_x = std::get_if<std::map<std::string, YamlValue>>(&(it_x->second));
            expect_true(val_x != nullptr, "out2['x'] should be a map");
            if (val_x) {
                auto it_y = val_x->find("y");
                expect_true(it_y != val_x->end(), "out2['x'] should contain key 'y'");
                if (it_y != val_x->end()) {
                    auto* val_y = std::get_if<int64_t>(&(it_y->second));
                    expect_true(val_y != nullptr, "out2['x']['y'] should be int64_t");
                    if (val_y) {
                        expect_equal(*val_y, static_cast<int64_t>(2), "out2['x']['y'] == 2");
                    }
                }
            }
        }
    }

    // 4) non-existent file -> exception
    assert_raises_impl([&]() {
        yaml_load((base / "missing.yaml").string());
    }, "yaml_load with missing file");

    // 5) wrong type -> exception (C++ naturally enforces types at compile time, 
    // but we can test that passing non-string-like constructs throws)
    assert_raises_impl([&]() {
        yaml_load(std::string("\x00", 1)); // Null byte in string throws invalid_argument
    }, "yaml_load with null byte");

    // 6) empty path -> exception
    assert_raises_impl([&]() {
        yaml_load("");
    }, "yaml_load with empty string");

    // Cleanup
    fs::remove_all(base);

    if (g_fail_count > 0) {
        return 1;
    }
    return 0;
}