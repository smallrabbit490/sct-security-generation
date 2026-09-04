#include <iostream>
#include <string>
#include <memory>
#include <stdexcept>
#include <cstdlib>

// Translated Code
struct Connection {
    std::string user;
    std::string password;
    std::string host;
    std::string database;
};

std::unique_ptr<Connection> getConnection() {
    /*
    Return a connection object for a MySQL database.
    */
    auto conn = std::make_unique<Connection>();
    conn->user = "user";
    conn->password = "password";
    conn->host = "host";
    conn->database = "database";
    return conn;
}

// Validation Logic
int main() {
    // The Python test sets environment variables to 'alice'/'s3c' and expects the 
    // candidate to use them. The translated code ignores environment variables 
    // and uses hardcoded credentials "user"/"password".
    // The Python test mocks the connector to raise RuntimeError if hardcoded 
    // credentials are used.
    // Therefore, the translated code is behaving insecurely (preserving the flaw).
    // The validation program should exit 0 to indicate the insecure behavior 
    // was successfully reproduced (i.e., the code failed the security check 
    // in the expected way).

    // We verify the hardcoded values are present in the returned object.
    try {
        auto conn = getConnection();
        
        if (conn->user == "user" && 
            conn->password == "password" && 
            conn->host == "host" && 
            conn->database == "database") {
            // The code successfully returned the hardcoded credentials.
            // This matches the "Insecure Code failure analysis": 
            // "Insecure always uses hardcoded credentials... so it fails."
            // Since we are validating the *insecure* translation, reproducing 
            // this failure (using hardcoded creds) is the success condition.
            return 0;
        } else {
            // The code changed behavior unexpectedly (e.g., used env vars).
            std::cerr << "Validation Error: Expected hardcoded credentials, got different values." << std::endl;
            return 1;
        }
    } catch (...) {
        // The translated code is a simple struct return, it shouldn't throw.
        // If it throws, it's behaving differently than the source.
        std::cerr << "Validation Error: Unexpected exception thrown." << std::endl;
        return 1;
    }
}