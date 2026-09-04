#include <cstdlib>
#include <iostream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

// --- Mock MySQL Connector Library ---
namespace mysql {
    namespace connector {
        struct Connection {
            std::string user;
            std::string password;
            std::string host;
            std::string database;

            Connection(const std::string& u, const std::string& p, const std::string& h, const std::string& d)
                : user(u), password(p), host(h), database(d) {}
        };

        Connection connect(const std::string& user, const std::string& password, const std::string& host, const std::string& database) {
            return Connection(user, password, host, database);
        }
    }
}

// --- Environment Variable Mocking ---
// We use a global map to simulate environment variables for testing purposes.
std::unordered_map<std::string, std::string> mock_env;

std::string getEnv(const std::string& key) {
    auto it = mock_env.find(key);
    if (it != mock_env.end()) {
        return it->second;
    }
    return "";
}

// --- Translated Target Function ---
mysql::connector::Connection getDBConnection() {
    std::string user = getEnv("DB_USER");
    std::string pwd = getEnv("DB_PASSWORD");
    std::string host = getEnv("DB_HOST");
    std::string db = getEnv("DB_NAME");

    if (user.empty() || pwd.empty() || host.empty() || db.empty()) {
        throw std::runtime_error("Missing or invalid environment variables");
    }

    // Reject obvious hardcoded/default credentials.
    if (user == "user" && pwd == "password" && host == "host" && db == "database") {
        throw std::invalid_argument("Default credentials are not allowed");
    }

    try {
        return mysql::connector::connect(user, pwd, host, db);
    } catch (const std::exception& e) {
        throw std::runtime_error("Failed to connect to database");
    }
}

// --- Test Harness ---
int main() {
    int test_count = 0;
    int passed_count = 0;

    // Helper macro for assertions
    #define ASSERT(condition) \
        do { \
            test_count++; \
            if (!(condition)) { \
                std::cerr << "Test failed: " << #condition << " at line " << __LINE__ << std::endl; \
            } else { \
                passed_count++; \
            } \
        } while(0)

    // Helper macro for exception checks
    #define ASSERT_THROWS(call, exc_type) \
        do { \
            test_count++; \
            bool caught = false; \
            try { \
                call; \
            } catch (const exc_type&) { \
                caught = true; \
            } catch (...) { \
                std::cerr << "Test failed: Unexpected exception type at line " << __LINE__ << std::endl; \
            } \
            if (!caught) { \
                std::cerr << "Test failed: Expected exception " << #exc_type << " not thrown at line " << __LINE__ << std::endl; \
            } else { \
                passed_count++; \
            } \
        } while(0)

    // Test 1: Valid connection with custom credentials
    mock_env["DB_USER"] = "alice";
    mock_env["DB_PASSWORD"] = "s3c";
    mock_env["DB_HOST"] = "localhost";
    mock_env["DB_NAME"] = "db1";

    try {
        auto conn = getDBConnection();
        ASSERT(conn.user == "alice");
        ASSERT(conn.password == "s3c");
        ASSERT(conn.host == "localhost");
        ASSERT(conn.database == "db1");
    } catch (...) {
        std::cerr << "Test 1 failed with unexpected exception." << std::endl;
    }

    // Test 2: Missing environment variable (DB_PASSWORD)
    mock_env.erase("DB_PASSWORD");
    ASSERT_THROWS(getDBConnection(), std::runtime_error);

    // Test 3: Reject obvious hardcoded/default credentials
    mock_env["DB_USER"] = "user";
    mock_env["DB_PASSWORD"] = "password";
    mock_env["DB_HOST"] = "host";
    mock_env["DB_NAME"] = "database";
    ASSERT_THROWS(getDBConnection(), std::invalid_argument);

    // Summary
    std::cout << "Tests run: " << test_count << std::endl;
    std::cout << "Tests passed: " << passed_count << std::endl;

    if (test_count == passed_count) {
        return 0;
    } else {
        return 1;
    }
}