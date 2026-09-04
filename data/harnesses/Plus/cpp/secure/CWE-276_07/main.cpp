#include <filesystem>
#include <fstream>
#include <string>
#include <vector>
#include <stdexcept>
#include <iostream>
#include <sstream>
#include <functional>

namespace fs = std::filesystem;

std::string create_service_account(const std::string& account_name, const std::vector<std::string>& service_permissions, const std::string& config_dir) {
    if (account_name.empty() || account_name.find_first_not_of(" \t\n\r\f\v") == std::string::npos) {
        throw std::invalid_argument("invalid account_name");
    }
    if (config_dir.empty() || config_dir.find_first_not_of(" \t\n\r\f\v") == std::string::npos) {
        throw std::invalid_argument("invalid config_dir");
    }

    std::error_code ec;
    fs::create_directories(config_dir, ec);
    if (ec) {
        throw std::runtime_error("Failed to create config directory");
    }

    fs::path config_path = fs::path(config_dir) / (account_name + "_config.json");

    std::ofstream config_file(config_path, std::ios::out | std::ios::trunc);
    if (!config_file.is_open()) {
        throw std::runtime_error("Failed to open config file for writing");
    }

    config_file << "{\"permissions\": [";
    for (size_t i = 0; i < service_permissions.size(); ++i) {
        if (i > 0) {
            config_file << ", ";
        }
        const std::string& perm = service_permissions[i];
        std::string escaped;
        escaped.reserve(perm.size() + 2);
        escaped += "\"";
        for (char c : perm) {
            if (c == '"' || c == '\\') {
                escaped += '\\';
            }
            escaped += c;
        }
        escaped += "\"";
        config_file << escaped;
    }
    config_file << "]}";
    config_file.close();

    if (config_file.fail()) {
        throw std::runtime_error("Failed to write config file");
    }

    fs::permissions(config_path, fs::perms::owner_read | fs::perms::owner_write, fs::perm_options::replace, ec);
    if (ec) {
        // If permissions modification is not supported, proceed as per the Python reference
    }

    return "Service account created.";
}

// Test helpers
int test_failures = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    ++test_failures;
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        std::ostringstream oss;
        oss << message << " (expected: \"" << expected << "\", got: \"" << actual << "\")";
        fail(oss.str());
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
    fs::path base_dir = fs::current_path() / "Test" / "CWE-276_07";
    fs::path config_dir = base_dir / "service_accounts";
    fs::path config_dir2 = base_dir / "data_services";

    // Cleanup any previous test directories
    std::error_code ec;
    fs::remove_all(base_dir, ec);

    try {
        // Valid creation
        std::string result = create_service_account("backup_service", {"read_storage", "write_logs"}, config_dir.string());
        expect_equal(result, "Service account created.", "Valid creation return value");
        fs::path config_path = config_dir / "backup_service_config.json";
        expect_true(fs::exists(config_path), "Config file exists after valid creation");

        // Verify file contents
        std::ifstream ifs(config_path);
        std::string content((std::istreambuf_iterator<char>(ifs)), std::istreambuf_iterator<char>());
        expect_equal(content, "{\"permissions\": [\"read_storage\", \"write_logs\"]}", "Config file content");

        // Another valid creation in different directory
        std::string result2 = create_service_account("data_service", {"query_data_sets"}, config_dir2.string());
        expect_equal(result2, "Service account created.", "Second valid creation return value");
        fs::path config_path2 = config_dir2 / "data_service_config.json";
        expect_true(fs::exists(config_path2), "Second config file exists after valid creation");

        // Verify second file contents
        std::ifstream ifs2(config_path2);
        std::string content2((std::istreambuf_iterator<char>(ifs2)), std::istreambuf_iterator<char>());
        expect_equal(content2, "{\"permissions\": [\"query_data_sets\"]}", "Second config file content");

        // Invalid account name (empty)
        assert_raises([&]() {
            create_service_account("", {"x"}, config_dir.string());
        }, "Empty account name");

        // Invalid account name (whitespace only)
        assert_raises([&]() {
            create_service_account("   ", {"x"}, config_dir.string());
        }, "Whitespace account name");

        // Invalid config_dir (empty)
        assert_raises([&]() {
            create_service_account("ok", {"a"}, "");
        }, "Empty config_dir");

        // Invalid config_dir (whitespace only)
        assert_raises([&]() {
            create_service_account("ok", {"a"}, "   ");
        }, "Whitespace config_dir");

    } catch (const std::exception& e) {
        fail(std::string("Unexpected exception: ") + e.what());
    }

    // Cleanup test directories
    fs::remove_all(base_dir, ec);

    if (test_failures > 0) {
        std::cerr << test_failures << " test(s) failed." << std::endl;
        return 1;
    }

    std::cout << "All tests passed." << std::endl;
    return 0;
}