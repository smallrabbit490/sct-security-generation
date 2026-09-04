#include <string>
#include <map>
#include <variant>
#include <vector>
#include <fstream>
#include <filesystem>
#include <stdexcept>
#include <sstream>
#include <iostream>
#include <cstdio>
#include <functional>

struct JsonValue;

using JsonObject = std::map<std::string, JsonValue>;
using JsonArray = std::vector<JsonValue>;

struct JsonValue {
    std::variant<std::nullptr_t, bool, int, double, std::string, JsonObject, JsonArray> data;
};

class json_exception : public std::runtime_error {
public:
    explicit json_exception(const std::string& msg) : std::runtime_error(msg) {}
};

static std::string escape_json_string(const std::string& s) {
    std::string o;
    o.reserve(s.size());
    for (char c : s) {
        switch (c) {
            case '"':  o += "\\\""; break;
            case '\\': o += "\\\\"; break;
            case '\b': o += "\\b"; break;
            case '\f': o += "\\f"; break;
            case '\n': o += "\\n"; break;
            case '\r': o += "\\r"; break;
            case '\t': o += "\\t"; break;
            default:
                if (static_cast<unsigned char>(c) < 0x20) {
                    char buf[7];
                    std::snprintf(buf, sizeof(buf), "\\u%04x", static_cast<unsigned char>(c));
                    o += buf;
                } else {
                    o += c;
                }
        }
    }
    return o;
}

static void write_json(std::ostream& os, const JsonValue& val) {
    std::visit([&os](const auto& v) {
        using T = std::decay_t<decltype(v)>;
        if constexpr (std::is_same_v<T, std::nullptr_t>) {
            os << "null";
        } else if constexpr (std::is_same_v<T, bool>) {
            os << (v ? "true" : "false");
        } else if constexpr (std::is_same_v<T, int>) {
            os << v;
        } else if constexpr (std::is_same_v<T, double>) {
            os << v;
        } else if constexpr (std::is_same_v<T, std::string>) {
            os << '"' << escape_json_string(v) << '"';
        } else if constexpr (std::is_same_v<T, JsonObject>) {
            os << '{';
            bool first = true;
            for (const auto& kv : v) {
                if (!first) os << ',';
                os << '"' << escape_json_string(kv.first) << "\":";
                write_json(os, kv.second);
                first = false;
            }
            os << '}';
        } else if constexpr (std::is_same_v<T, JsonArray>) {
            os << '[';
            bool first = true;
            for (const auto& item : v) {
                if (!first) os << ',';
                write_json(os, item);
                first = false;
            }
            os << ']';
        }
    }, val.data);
}

std::string create_config_file(const JsonObject& config_data, const std::string& file_path) {
    if (file_path.empty() || file_path.find_first_not_of(" \t\n\r\f\v") == std::string::npos) {
        throw std::invalid_argument("invalid file_path");
    }

    std::filesystem::path p(file_path);
    std::filesystem::path parent = p.parent_path();

    std::error_code ec;
    if (!parent.empty()) {
        std::filesystem::create_directories(parent, ec);
        if (ec) {
            throw std::runtime_error("Failed to create directories: " + ec.message());
        }
    }

    std::ofstream file(p, std::ios::out | std::ios::trunc);
    if (!file.is_open()) {
        throw std::runtime_error("Failed to open file for writing: " + file_path);
    }

    JsonValue root;
    root.data = config_data;
    write_json(file, root);

    file.close();
    if (file.fail()) {
        throw std::runtime_error("Failed to write to file: " + file_path);
    }

    std::filesystem::permissions(p,
        std::filesystem::perms::owner_read | std::filesystem::perms::owner_write,
        std::filesystem::perm_options::replace, ec);

    if (ec) {
        throw std::runtime_error("Failed to set file permissions: " + ec.message());
    }

    return "Configuration file created.";
}

// Test helpers
int test_fail_count = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    test_fail_count++;
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected: '" + expected + "', got: '" + actual + "')");
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Expected
    } catch (...) {
        // Expected
    }
}

int main() {
    std::string base_dir = "./Test/CWE-276_08";
    std::filesystem::create_directories(base_dir);

    std::string path = base_dir + "/app_config.json";
    std::string path2 = base_dir + "/nested/cfg.json";
    std::string bad_path = base_dir + "/bad.json";

    // Cleanup any previous test artifacts
    std::filesystem::remove(path);
    std::filesystem::remove(path2);
    std::filesystem::remove(bad_path);
    std::filesystem::remove(base_dir + "/nested");

    try {
        // Test 1: Basic config creation
        JsonObject config1;
        config1["setting"] = JsonValue{std::string("value")};
        std::string result1 = create_config_file(config1, path);
        expect_equal(result1, "Configuration file created.", "Test 1 return value");
        expect_true(std::filesystem::exists(path), "Test 1 file exists");

        // Verify permissions (owner_read | owner_write)
        std::error_code ec;
        auto perms = std::filesystem::status(path, ec).permissions();
        expect_true(!ec, "Test 1 permissions read successfully");
        if (!ec) {
            auto owner_perms = perms & std::filesystem::perms::owner_all;
            expect_true(owner_perms == (std::filesystem::perms::owner_read | std::filesystem::perms::owner_write),
                        "Test 1 file permissions are 0600");
        }

        // Test 2: Nested directory creation
        JsonObject config2;
        config2["a"] = JsonValue{1};
        std::string result2 = create_config_file(config2, path2);
        expect_equal(result2, "Configuration file created.", "Test 2 return value");
        expect_true(std::filesystem::exists(path2), "Test 2 file exists");

        perms = std::filesystem::status(path2, ec).permissions();
        expect_true(!ec, "Test 2 permissions read successfully");
        if (!ec) {
            auto owner_perms = perms & std::filesystem::perms::owner_all;
            expect_true(owner_perms == (std::filesystem::perms::owner_read | std::filesystem::perms::owner_write),
                        "Test 2 file permissions are 0600");
        }

        // Test 3: Empty file_path
        assert_raises([]() {
            JsonObject c;
            create_config_file(c, "");
        }, "Test 3 empty file_path");

        // Test 4: Whitespace-only file_path
        assert_raises([]() {
            JsonObject c;
            create_config_file(c, "   \t\n  ");
        }, "Test 4 whitespace file_path");

        // Test 5: Invalid file_path (simulating None/null by bypassing strong typing)
        assert_raises([]() {
            JsonObject c;
            create_config_file(c, std::string{});
        }, "Test 5 null/empty file_path");

    } catch (const std::exception& e) {
        fail("Unexpected exception in test execution: " + std::string(e.what()));
    }

    // Cleanup
    std::filesystem::remove(path);
    std::filesystem::remove(path2);
    std::filesystem::remove(bad_path);
    std::filesystem::remove_all(base_dir);

    if (test_fail_count > 0) {
        std::cerr << test_fail_count << " test(s) failed." << std::endl;
        return 1;
    }

    std::cout << "All tests passed." << std::endl;
    return 0;
}