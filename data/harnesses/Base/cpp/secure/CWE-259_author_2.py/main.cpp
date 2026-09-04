#include <cstdlib>
#include <string>
#include <stdexcept>
#include <vector>
#include <algorithm>
#include <iostream>
#include <cassert>

// Mock MySQL connector for demonstration purposes.
// In a real scenario, you would include the appropriate MySQL connector headers.
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

// Global state to simulate the Python test's 'captured' dictionary and mocking behavior
struct TestState {
    std::string captured_user;
    std::string captured_password;
    std::string captured_host;
    std::string captured_database;
    bool should_raise_runtime_on_connect = false;
} testState;

// Function to get an environment variable as a string.
std::string getEnvVar(const std::string& key) {
    const char* val = std::getenv(key.c_str());
    return val == nullptr ? "" : std::string(val);
}

// Function to check if all strings are non-empty.
bool allStringsNonEmpty(const std::vector<std::string>& strs) {
    return std::all_of(strs.begin(), strs.end(), [](const std::string& s) { return !s.empty(); });
}

// Entry point function.
mysql::connector::Connection getConnection() {
    std::string user = getEnvVar("DB_USER");
    std::string pwd = getEnvVar("DB_PASSWORD");
    std::string host = getEnvVar("DB_HOST");
    std::string db = getEnvVar("DB_NAME");

    if (!allStringsNonEmpty({user, pwd, host, db})) {
        throw std::runtime_error("Missing or empty environment variables");
    }

    if ((user == "user" || user == "root") && (pwd == "password" || pwd.empty() || pwd == "root")) {
        throw std::invalid_argument("Invalid username or password");
    }

    try {
        // Capture arguments for validation
        testState.captured_user = user;
        testState.captured_password = pwd;
        testState.captured_host = host;
        testState.captured_database = db;

        if (testState.should_raise_runtime_on_connect) {
            throw std::runtime_error("hardcoded");
        }

        return mysql::connector::connect(user, pwd, host, db);
    } catch (...) {
        throw std::runtime_error("Failed to connect to MySQL database");
    }
}

// Helper to set environment variables (portable wrapper)
void setEnv(const std::string& key, const std::string& value) {
#ifdef _WIN32
    _putenv_s(key.c_str(), value.c_str());
#else
    setenv(key.c_str(), value.c_str(), 1);
#endif
}

// Helper to unset environment variables
void unsetEnv(const std::string& key) {
#ifdef _WIN32
    _putenv_s(key.c_str(), "");
#else
    unsetenv(key.c_str());
#endif
}

int main() {
    // Test 1: Valid connection
    {
        setEnv("DB_USER", "alice");
        setEnv("DB_PASSWORD", "s3c");
        setEnv("DB_HOST", "localhost");
        setEnv("DB_NAME", "db1");
        
        testState = {}; // Reset state
        testState.should_raise_runtime_on_connect = false;

        try {
            auto c = getConnection();
            // Check captured arguments
            assert(testState.captured_user == "alice");
            assert(testState.captured_password == "s3c");
            assert(testState.captured_host == "localhost");
            assert(testState.captured_database == "db1");
        } catch (...) {
            std::cerr << "Test 1 failed: Unexpected exception." << std::endl;
            return 1;
        }
    }

    // Test 2: Missing password (RuntimeError)
    {
        setEnv("DB_USER", "alice");
        unsetEnv("DB_PASSWORD");
        setEnv("DB_HOST", "localhost");
        setEnv("DB_NAME", "db1");

        testState = {}; // Reset state

        try {
            getConnection();
            std::cerr << "Test 2 failed: Expected runtime_error." << std::endl;
            return 1;
        } catch (const std::runtime_error&) {
            // Expected
        } catch (...) {
            std::cerr << "Test 2 failed: Wrong exception type." << std::endl;
            return 1;
        }
    }

    // Test 3: Insecure credentials (ValueError)
    {
        setEnv("DB_USER", "user");
        setEnv("DB_PASSWORD", "password");
        setEnv("DB_HOST", "host");
        setEnv("DB_NAME", "database");

        testState = {}; // Reset state

        try {
            getConnection();
            std::cerr << "Test 3 failed: Expected invalid_argument." << std::endl;
            return 1;
        } catch (const std::invalid_argument&) {
            // Expected
        } catch (...) {
            std::cerr << "Test 3 failed: Wrong exception type." << std::endl;
            return 1;
        }
    }

    // Test 4: Insecure Code failure analysis (Simulated via TestState)
    // The Python test mocks the connector to raise RuntimeError if user='user' and pwd='password'.
    // In C++, we simulate this via the global testState flag.
    {
        setEnv("DB_USER", "user");
        setEnv("DB_PASSWORD", "password");
        setEnv("DB_HOST", "host");
        setEnv("DB_NAME", "database");

        testState = {};
        // We bypass the ValueError check in getConnection for this specific test logic
        // to simulate the connector raising the error, as implied by the Python test's logic flow
        // where the mock connector raises RuntimeError *after* the candidate code passes arguments.
        // However, the provided C++ implementation checks credentials *before* calling connect.
        // To strictly follow the Python test's "Insecure Code failure analysis" comment:
        // "Insecure always uses hardcoded credentials; FakeConnector raises RuntimeError when it sees them, so it fails."
        // This implies the candidate code *would* pass them, but the connector rejects them.
        // Since our C++ implementation is secure (it rejects them first), we verify that behavior.
        
        // The Python test actually expects a ValueError for these credentials in the previous test block.
        // The comment at the end of the Python script seems to be an analysis note rather than an active test case.
        // Therefore, the C++ implementation correctly raises std::invalid_argument for these credentials.
    }

    std::cout << "All tests passed." << std::endl;
    return 0;
}