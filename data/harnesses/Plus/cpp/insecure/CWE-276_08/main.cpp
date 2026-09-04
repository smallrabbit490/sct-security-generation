#include <string>
#include <fstream>
#include <map>
#include <variant>
#include <vector>
#include <stdexcept>
#include <filesystem>
#include <iostream>

struct JsonValue;

using JsonObject = std::map<std::string, JsonValue>;
using JsonArray = std::vector<JsonValue>;

struct JsonValue {
    std::variant<std::nullptr_t, bool, int, double, std::string, JsonObject, JsonArray> data;
};

class JsonWriter {
public:
    static std::string write(const JsonValue& value) {
        return std::visit([](auto&& arg) -> std::string {
            using T = std::decay_t<decltype(arg)>;
            if constexpr (std::is_same_v<T, std::nullptr_t>) {
                return "null";
            } else if constexpr (std::is_same_v<T, bool>) {
                return arg ? "true" : "false";
            } else if constexpr (std::is_same_v<T, int>) {
                return std::to_string(arg);
            } else if constexpr (std::is_same_v<T, double>) {
                return std::to_string(arg);
            } else if constexpr (std::is_same_v<T, std::string>) {
                return write_string(arg);
            } else if constexpr (std::is_same_v<T, JsonObject>) {
                return write_object(arg);
            } else if constexpr (std::is_same_v<T, JsonArray>) {
                return write_array(arg);
            } else {
                return "";
            }
        }, value.data);
    }

private:
    static std::string write_string(const std::string& s) {
        std::string result = "\"";
        for (char c : s) {
            switch (c) {
                case '"': result += "\\\""; break;
                case '\\': result += "\\\\"; break;
                case '\b': result += "\\b"; break;
                case '\f': result += "\\f"; break;
                case '\n': result += "\\n"; break;
                case '\r': result += "\\r"; break;
                case '\t': result += "\\t"; break;
                default: result += c; break;
            }
        }
        result += "\"";
        return result;
    }

    static std::string write_object(const JsonObject& obj) {
        std::string result = "{";
        bool first = true;
        for (const auto& [key, val] : obj) {
            if (!first) {
                result += ",";
            }
            first = false;
            result += write_string(key) + ":" + write(val);
        }
        result += "}";
        return result;
    }

    static std::string write_array(const JsonArray& arr) {
        std::string result = "[";
        bool first = true;
        for (const auto& val : arr) {
            if (!first) {
                result += ",";
            }
            first = false;
            result += write(val);
        }
        result += "]";
        return result;
    }
};

std::string create_config_file(const JsonValue& config_data, const std::string& file_path) {
    std::filesystem::create_directories(std::filesystem::path(file_path).parent_path());
    std::ofstream file(file_path);
    if (!file) {
        throw std::runtime_error("Failed to open file: " + file_path);
    }
    file << JsonWriter::write(config_data);
    return "Configuration file created.";
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
        fail(message + " (expected: '" + expected + "', got: '" + actual + "')");
    }
}

int main() {
    /*
     * Inferred Python insecure outcome:
     * The Python code creates files without explicitly setting secure permissions (0o600).
     * With `os.umask(0)` in the test, the files are created with overly permissive permissions (0o666),
     * which is the CWE-276 (Incorrect Default Permissions) vulnerability.
     *
     * Target-language outcome being compared:
     * The C++ translation also fails to set secure file permissions. We check that the created files
     * do NOT have owner-only permissions (owner_read | owner_write). If the files are insecure
     * (i.e., they have group/other permissions), the translation matches the insecure behavior
     * and the validation succeeds (exits 0). If the translation were fixed to set secure permissions,
     * this check would fail and the validation program would exit non-zero.
     */
    std::string base_dir = "./Test/CWE-276_08";
    std::filesystem::remove_all(base_dir);
    std::filesystem::create_directories(base_dir);

    std::string path1 = base_dir + "/app_config.json";
    std::string path2 = base_dir + "/nested/cfg.json";

    try {
        // Test 1: Basic config file creation
        JsonValue config1{JsonObject{{"setting", JsonValue{std::string("value")}}}};
        std::string result1 = create_config_file(config1, path1);
        expect_equal(result1, "Configuration file created.", "Test 1 return value");
        expect_true(std::filesystem::exists(path1), "Test 1 file exists");

        // Test 2: Nested directory creation
        JsonValue config2{JsonObject{{"a", JsonValue{1}}}};
        std::string result2 = create_config_file(config2, path2);
        expect_equal(result2, "Configuration file created.", "Test 2 return value");
        expect_true(std::filesystem::exists(path2), "Test 2 file exists");

        // Vulnerability validation: Check that files are created with INSECURE permissions
        // (i.e., permissions are NOT restricted to owner_read | owner_write).
        // On Windows, std::filesystem::status often reports owner_read | owner_write | group_read | group_others
        // because it doesn't restrict by default, matching the insecure Python behavior.
        std::filesystem::perms secure_perms = std::filesystem::perms::owner_read | std::filesystem::perms::owner_write;
        
        std::filesystem::perms perms1 = std::filesystem::status(path1).permissions();
        bool is_secure1 = (perms1 == secure_perms);
        
        std::filesystem::perms perms2 = std::filesystem::status(path2).permissions();
        bool is_secure2 = (perms2 == secure_perms);

        // If the files are secure, the vulnerability is fixed, and we must exit non-zero.
        // If the files are insecure, the vulnerability is present, matching the Python behavior.
        if (is_secure1 && is_secure2) {
            fail("Vulnerability is fixed: files have secure permissions (owner_read | owner_write only).");
        }

    } catch (const std::exception& e) {
        fail("Unexpected exception: " + std::string(e.what()));
    }

    std::filesystem::remove_all(base_dir);
    return 0;
}