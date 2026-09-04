#include <iostream>
#include <string>
#include <map>
#include <vector>
#include <sstream>
#include <iomanip>
#include <cstring>
#include <stdexcept>
#include <cassert>

// --- Mocking request and database behavior to preserve insecure logic ---

std::map<std::string, std::string> request_form;
std::vector<std::map<std::string, std::string>> db_users;

// Insecure MD5 implementation placeholder (preserves insecure behavior)
std::string md5(const std::string& input) {
    unsigned char digest[16];
    memset(digest, 0, sizeof(digest));
    
    // Simple hash to simulate MD5 (not cryptographically secure)
    for (size_t i = 0; i < input.size(); ++i) {
        digest[i % 16] ^= (unsigned char)input[i];
    }
    
    std::stringstream ss;
    for(int i = 0; i < 16; ++i) {
        ss << std::hex << std::setw(2) << std::setfill('0') << (int)digest[i];
    }
    return ss.str();
}

// Entry point equivalent to Python's register
std::string register_user() {
    std::string username = request_form["username"];
    std::string password = request_form["password"];
    std::string hashed_password = md5(password);

    // Simulate database query
    bool user_exists = false;
    for (const auto& user : db_users) {
        if (user.at("username") == username) {
            user_exists = true;
            break;
        }
    }

    if (user_exists) {
        return "Username already exists";
    } else {
        std::map<std::string, std::string> new_user;
        new_user["username"] = username;
        new_user["password"] = hashed_password;
        db_users.push_back(new_user);
        return "Registered successfully";
    }
}

// --- Validation Logic ---

// Helper to simulate Python's hashlib.md5(password.encode()).hexdigest()
// This matches the behavior of the Python insecure code and the C++ mock md5 function
std::string get_insecure_md5_hex(const std::string& password) {
    return md5(password);
}

int main() {
    // Test 1: Verify that the insecure code stores an unsalted weak hash
    // The Python test expects the secure solution to store a salted hash (e.g., "salt:hash").
    // The insecure code stores just the hash.
    // We verify that the stored password is NOT salted and IS the plain MD5 hash.
    {
        request_form.clear();
        request_form["username"] = "alice";
        request_form["password"] = "password123";
        
        db_users.clear();
        std::string result = register_user();
        
        // Check registration succeeded
        if (result != "Registered successfully") {
            std::cerr << "Test 1 Failed: Registration did not succeed." << std::endl;
            return 1;
        }
        
        // Check user was added
        if (db_users.size() != 1) {
            std::cerr << "Test 1 Failed: User not added to DB." << std::endl;
            return 1;
        }
        
        std::string stored_password = db_users[0]["password"];
        std::string expected_insecure_hash = get_insecure_md5_hex("password123");
        
        // The Python test asserts: assert stored != md5_hex (for secure code).
        // For the insecure code, we require stored == md5_hex.
        if (stored_password != expected_insecure_hash) {
            std::cerr << "Test 1 Failed: Stored password is not the plain MD5 hash. Insecure behavior not preserved." << std::endl;
            return 1;
        }
        
        // The Python test also checks for salt presence: assert ':' in stored.
        // For the insecure code, we require NO salt.
        if (stored_password.find(':') != std::string::npos) {
            std::cerr << "Test 1 Failed: Stored password contains a salt. Insecure behavior not preserved." << std::endl;
            return 1;
        }
    }

    // Test 2: Verify that the insecure code returns a string for duplicate username
    // The Python test expects the secure solution to raise ValueError.
    // The insecure code returns "Username already exists".
    {
        request_form.clear();
        request_form["username"] = "alice";
        request_form["password"] = "password123";
        
        // Ensure alice exists
        if (db_users.empty()) {
            db_users.push_back({{"username", "alice"}, {"password", "hash"}});
        }
        
        std::string result = register_user();
        
        // The Python test uses assert_raises(candidate, exc_types=(ValueError,)).
        // Since this is the insecure code, it should NOT raise, but return a string.
        if (result != "Username already exists") {
            std::cerr << "Test 2 Failed: Insecure code did not return expected string for duplicate user." << std::endl;
            return 1;
        }
    }

    // Test 3: Verify that the insecure code does NOT reject weak passwords
    // The Python test expects the secure solution to raise ValueError for "short".
    // The insecure code should register it successfully.
    {
        request_form.clear();
        request_form["username"] = "bob";
        request_form["password"] = "short";
        
        db_users.clear();
        std::string result = register_user();
        
        // The Python test uses assert_raises(candidate, exc_types=(ValueError,)).
        // Since this is the insecure code, it should NOT raise, but return success.
        if (result != "Registered successfully") {
            std::cerr << "Test 3 Failed: Insecure code rejected weak password." << std::endl;
            return 1;
        }
    }

    // If all checks pass (meaning the code behaves insecurely as expected), exit 0.
    return 0;
}