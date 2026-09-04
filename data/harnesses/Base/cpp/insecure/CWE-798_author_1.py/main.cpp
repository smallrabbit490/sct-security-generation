#include <iostream>
#include <string>
#include <cstdlib>
#include <stdexcept>
#include <vector>
#include <map>

// Mocking the MySQL Connector/C++ headers to allow compilation without the library
namespace sql {
    class Connection {
    public:
        virtual ~Connection() {}
    };
    namespace mysql {
        class MySQL_Driver {
        public:
            virtual ~MySQL_Driver() {}
            virtual Connection* connect(const std::string& host, const std::string& user, const std::string& password) = 0;
        };
        // Mock global instance
        MySQL_Driver* get_mysql_driver_instance();
    }
}

// Global driver pointer as per the translated code
sql::mysql::MySQL_Driver* driver;

// ---------------------------------------------------------
// Translated Code (Target for validation)
// ---------------------------------------------------------

sql::Connection* getDBConnection() {
    /*
    Return a MySQL database connection.
    */
    driver = sql::mysql::get_mysql_driver_instance();
    return driver->connect("tcp://host:3306", "user", "password");
}

// ---------------------------------------------------------
// Mock Implementation for Testing
// ---------------------------------------------------------

// Structure to capture arguments passed to the mock connect function
struct ConnectionParams {
    std::string host;
    std::string user;
    std::string password;
};

ConnectionParams g_captured_params;
bool g_should_fail = false;

class MockDriver : public sql::mysql::MySQL_Driver {
public:
    sql::Connection* connect(const std::string& host, const std::string& user, const std::string& password) override {
        g_captured_params.host = host;
        g_captured_params.user = user;
        g_captured_params.password = password;
        
        if (g_should_fail) {
            throw std::runtime_error("Mock connection failure");
        }
        // Return a dummy non-null pointer
        static int dummy_conn;
        return reinterpret_cast<sql::Connection*>(&dummy_conn);
    }
};

MockDriver mock_instance;

namespace sql {
    namespace mysql {
        MySQL_Driver* get_mysql_driver_instance() {
            return &mock_instance;
        }
    }
}

// ---------------------------------------------------------
// Validation Logic
// ---------------------------------------------------------

void assert_raises(bool condition, const std::string& msg) {
    if (!condition) {
        std::cerr << "Assertion failed: " << msg << std::endl;
        std::exit(1);
    }
}

int main() {
    // Setup environment variables for the first test case
    // Note: The translated C++ code does not use getenv, but the Python test logic
    // implies that a secure version would. We set them to verify the C++ code 
    // ignores them (insecure behavior).
    _putenv_s("DB_USER", "alice");
    _putenv_s("DB_PASSWORD", "s3c");
    _putenv_s("DB_HOST", "localhost");
    _putenv_s("DB_NAME", "db1");

    // Test 1: Check if the code uses environment variables
    // Expected Insecure Behavior: The code ignores env vars and uses hardcoded values.
    // If the code were secure, it would use 'alice' and 's3c'.
    // Since it is insecure, it uses 'user' and 'password'.
    
    sql::Connection* conn = getDBConnection();
    
    // The Python test expects: assert captured['user'] == 'alice'
    // The Insecure C++ code provides: captured['user'] == 'user'
    // Therefore, for the validation to pass (detecting the vulnerability),
    // we check that the captured value is NOT the expected secure value.
    
    if (g_captured_params.user == "alice" && g_captured_params.password == "s3c") {
        std::cerr << "Validation Failed: Code used environment variables (Secure behavior detected)." << std::endl;
        return 1;
    }

    // Verify it matches the hardcoded insecure values
    if (g_captured_params.user != "user" || g_captured_params.password != "password") {
        std::cerr << "Validation Failed: Code did not use expected hardcoded credentials." << std::endl;
        return 1;
    }

    // Test 2: Missing env var check
    // Python test: os.environ.pop('DB_PASSWORD', None); assert_raises(...)
    // Insecure C++ code does not check env vars, so it will NOT raise.
    // The Python test expects a RuntimeError here for a secure implementation.
    // For the insecure implementation, it succeeds (returns connection).
    // The validation rule says: "If the secure test expects the secure solution to pass 
    // and the Python insecure code is expected to fail, make the target program treat 
    // that matching failure as success."
    // Here, the Python test expects the candidate to FAIL (raise RuntimeError) because 
    // the password is missing. The insecure code SUCCEEDS (ignores missing env var).
    // This is a mismatch in behavior. However, the primary vulnerability is the hardcoding.
    // The Python test logic for "missing env" assumes the code reads env vars. 
    // Since the C++ code never reads env vars, this test is technically N/A for the C++ code's logic flow,
    // but strictly speaking, the behavior differs (Success vs Exception).
    // Given the "Insecure Code failure analysis": "Insecure always uses hardcoded credentials; 
    // under these tests it cannot use env-provided values and fails the captured-parameter assertions."
    // We have already validated the captured parameter assertion failure (Test 1).
    // We will skip the exception check for missing env vars because the C++ code 
    // doesn't implement the logic that would trigger it (reading env vars).

    // Test 3: Reject obvious hardcoded tuple
    // Python test: sets env vars to 'user', 'password', etc. and asserts it raises ValueError.
    // Secure code would read these and realize they are default/bad values and raise.
    // Insecure code uses these hardcoded values regardless.
    // So the insecure code returns a connection (Success), while the test expects Failure.
    // This confirms the vulnerability is present (the code accepts the hardcoded bad values).
    // We verify that the code indeed runs successfully with these bad values set in env.
    
    _putenv_s("DB_USER", "user");
    _putenv_s("DB_PASSWORD", "password");
    _putenv_s("DB_HOST", "host");
    _putenv_s("DB_NAME", "database");

    g_captured_params = {}; // Reset
    conn = getDBConnection();

    if (g_captured_params.user != "user" || g_captured_params.password != "password") {
        std::cerr << "Validation Failed: Hardcoded values changed unexpectedly." << std::endl;
        return 1;
    }

    // If we reached here, the code consistently uses hardcoded credentials,
    // ignores environment variables, and does not implement security checks.
    // This matches the "Insecure" profile.
    std::cout << "Validation Passed: Insecure behavior confirmed (hardcoded credentials used)." << std::endl;
    return 0;
}