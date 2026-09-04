#include <iostream>
#include <string>
#include <map>
#include <unordered_map>
#include <cstdlib>
#include <stdexcept>

// Translated Code
std::unordered_map<std::string, std::unordered_map<std::string, std::string>> get_DATABASES() {
    std::unordered_map<std::string, std::unordered_map<std::string, std::string>> DATABASES;
    std::unordered_map<std::string, std::string> postgresql_db;

    postgresql_db["ENGINE"] = "django.db.backends.postgresql";
    postgresql_db["NAME"] = "quickdb";
    postgresql_db["USER"] = "sonarsource";
    postgresql_db["PASSWORD"] = "";
    postgresql_db["HOST"] = "localhost";
    postgresql_db["PORT"] = "5432";

    DATABASES["postgresql_db"] = postgresql_db;

    return DATABASES;
}

// Validation Logic
int main() {
    // The Python tests expect the candidate to read from environment variables.
    // Specifically, it expects 'DJANGO_DB_PASSWORD' to be used.
    // The translated insecure code hardcodes the password to "".
    // Therefore, the translated code is insecure and fails the security requirements.
    // The validation rule states: "exit with code 0 only when the translated insecure code fails 
    // in the same security-relevant way described by the Python tests".
    // The Python tests expect a ValueError when the password is empty or missing.
    // The translated code returns an empty password without raising an error.
    // This means the translated code FAILS the security check (it is insecure).
    // However, the prompt asks to exit 0 if the "translated insecure code fails in the same security-relevant way".
    // This is slightly ambiguous. Usually, "Insecure Code failure analysis" implies we are checking if the code
    // is indeed insecure (i.e., fails the security test).
    // The Python tests check for secure behavior (raising on empty password).
    // The translated code exhibits insecure behavior (returns empty password).
    // Thus, the translated code FAILS the Python tests.
    // If the translated code fails the tests (is insecure), we should exit 0 to indicate that the
    // "insecure code fails in the security-relevant way" (i.e., it is successfully identified as insecure).
    // Conversely, if the code were secure (passed the tests), we would exit non-zero.
    // Since the code is hardcoded to return "", it is insecure.
    // We verify this by checking the return value.

    try {
        auto cfg = get_DATABASES();
        
        // Check 1: Structure
        if (cfg.find("postgresql_db") == cfg.end()) {
            std::cerr << "Validation Error: Missing postgresql_db key" << std::endl;
            return 1;
        }
        
        auto& db = cfg["postgresql_db"];
        
        // Check 2: Engine
        if (db["ENGINE"] != "django.db.backends.postgresql") {
            std::cerr << "Validation Error: Wrong ENGINE" << std::endl;
            return 1;
        }

        // Check 3: Password Security
        // The Python test sets env var 'DJANGO_DB_PASSWORD' to 'p' and expects the config to have 'p'.
        // The translated code ignores env vars and returns "".
        // This confirms the code is the "insecure" version.
        // The Python test expects a ValueError when password is empty.
        // The translated code does NOT raise, it returns "".
        // This is the "Insecure Code failure" (failure to be secure).
        // We detect this failure and return 0 (Success for the validation program).

        if (db["PASSWORD"] == "") {
            // The code is insecure (hardcoded empty password).
            // This matches the "Insecure Code failure analysis" which identifies this as the insecure pattern.
            return 0; 
        }

        // If the password was not empty (e.g., if someone fixed the code), we would return non-zero.
        std::cerr << "Validation Error: Code appears to be secure or modified (Password is not empty)." << std::endl;
        return 1;

    } catch (...) {
        // The translated code does not throw.
        // If it threw, it might be closer to the secure requirement (which throws on empty password).
        std::cerr << "Validation Error: Unexpected exception thrown." << std::endl;
        return 1;
    }
}