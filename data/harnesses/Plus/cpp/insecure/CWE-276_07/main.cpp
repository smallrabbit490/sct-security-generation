#include <filesystem>
#include <fstream>
#include <string>
#include <vector>
#include <stdexcept>
#include <iostream>

namespace fs = std::filesystem;

// Inferred Python insecure outcome:
// The Python code creates directories and files without restricting their permissions.
// When os.umask(0) is set, the files and directories are created with overly permissive 
// permissions (e.g., 0o777 for directories and 0o666 for files). The Python tests expect 
// restricted permissions (0o700 for dirs, 0o600 for files), which the insecure code fails to provide.
// Thus, the insecure Python code produces files/dirs that are NOT restricted.

std::string create_service_account(const std::string& account_name, const std::vector<std::string>& service_permissions, const std::string& config_dir) {
    fs::create_directories(config_dir);
    
    std::string config_path = (fs::path(config_dir) / (account_name + "_config.json")).string();
    
    std::ofstream config_file(config_path);
    if (!config_file.is_open()) {
        throw std::runtime_error("Failed to open config file for writing.");
    }
    
    config_file << "{\"permissions\": [";
    for (size_t i = 0; i < service_permissions.size(); ++i) {
        config_file << "\"" << service_permissions[i] << "\"";
        if (i < service_permissions.size() - 1) {
            config_file << ", ";
        }
    }
    config_file << "]}";
    
    if (config_file.fail()) {
        throw std::runtime_error("Failed to write to config file.");
    }
    
    return "Service account created with default permissions.";
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

int main() {
    std::string base_dir = "./Test/CWE-276_07";
    fs::create_directories(base_dir);

    std::string config_dir = base_dir + "/service_accounts";
    std::string config_dir2 = base_dir + "/data_services";

    // Clean up any previous test runs
    fs::remove_all(config_dir);
    fs::remove_all(config_dir2);

    // Create the first service account
    std::string account_name1 = "backup_service";
    std::vector<std::string> permissions1 = {"read_storage", "write_logs"};
    create_service_account(account_name1, permissions1, config_dir);

    std::string config_path1 = (fs::path(config_dir) / (account_name1 + "_config.json")).string();
    
    // Target-language outcome being compared:
    // The C++ translation also fails to restrict permissions. 
    // fs::status(...).permissions() will return the default (permissive) permissions.
    // We check that the permissions are NOT restricted (i.e., they do not equal owner_read | owner_write).
    fs::perms file_perms1 = fs::status(config_path1).permissions();
    bool is_file1_restricted = (file_perms1 == (fs::perms::owner_read | fs::perms::owner_write));
    
    fs::perms dir_perms1 = fs::status(config_dir).permissions();
    bool is_dir1_restricted = (dir_perms1 == (fs::perms::owner_read | fs::perms::owner_write | fs::perms::owner_exec));

    // Create the second service account
    std::string account_name2 = "data_service";
    std::vector<std::string> permissions2 = {"query_data_sets"};
    create_service_account(account_name2, permissions2, config_dir2);

    std::string config_path2 = (fs::path(config_dir2) / (account_name2 + "_config.json")).string();

    fs::perms file_perms2 = fs::status(config_path2).permissions();
    bool is_file2_restricted = (file_perms2 == (fs::perms::owner_read | fs::perms::owner_write));
    
    fs::perms dir_perms2 = fs::status(config_dir2).permissions();
    bool is_dir2_restricted = (dir_perms2 == (fs::perms::owner_read | fs::perms::owner_write | fs::perms::owner_exec));

    // The insecure code should result in files and directories that are NOT restricted.
    // If they are restricted, the vulnerability was fixed, and we must exit non-zero.
    expect_true(!is_file1_restricted, "File 1 permissions should not be restricted (insecure behavior expected)");
    expect_true(!is_dir1_restricted, "Dir 1 permissions should not be restricted (insecure behavior expected)");
    expect_true(!is_file2_restricted, "File 2 permissions should not be restricted (insecure behavior expected)");
    expect_true(!is_dir2_restricted, "Dir 2 permissions should not be restricted (insecure behavior expected)");

    // Clean up
    fs::remove_all(base_dir);

    return 0;
}