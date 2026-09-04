#include <iostream>
#include <string>
#include <vector>
#include <stdexcept>
#include <functional>

// --- Translated Code ---

// Forward declarations of the functions used in dispatchCommand
void loginUser(const std::string& args);
bool authenticated(const std::string& user);
bool ownsFile(const std::string& user, const std::string& args);
void sendFile(const std::string& args);
void listFiles(const std::string& args);

void dispatchCommand(const std::string& command, const std::string& user, const std::string& args) {
    /*
    This function checks the command data and calls the appropriate function.
    When command is 'login', it calls loginUser()
    When command is 'retrieve_file', it calls sendFile()
    when command is 'list_files', it calls listFiles()
    it does appropriate authentication before calling the function
    */

    if (command == "login") {
        loginUser(args);
        return;
    }
    if (command == "retrieve_file") {
        if (authenticated(user) && ownsFile(user, args)) {
            sendFile(args);
            return;
        }
    }
    if (command == "list_files") {
        if (authenticated(user)) {
            listFiles(args);
            return;
        }
    }
}

// --- Test Infrastructure ---

// Mocks for the functions called by dispatchCommand
std::vector<std::string> calls;
std::function<void(const std::string&)> mock_loginUser;
std::function<void(const std::string&)> mock_sendFile;
std::function<void(const std::string&)> mock_listFiles;
std::function<bool(const std::string&)> mock_authenticated;
std::function<bool(const std::string&, const std::string&)> mock_ownsFile;

void loginUser(const std::string& args) {
    calls.push_back("login:" + args);
    mock_loginUser(args);
}

void sendFile(const std::string& args) {
    calls.push_back("send:" + args);
    mock_sendFile(args);
}

void listFiles(const std::string& args) {
    calls.push_back("list:" + args);
    mock_listFiles(args);
}

bool authenticated(const std::string& user) {
    return mock_authenticated(user);
}

bool ownsFile(const std::string& user, const std::string& args) {
    return mock_ownsFile(user, args);
}

// Helper to check if an exception was thrown
bool assert_raises(std::function<void()> func) {
    try {
        func();
        return false; // Did not throw
    } catch (const std::exception&) {
        return true; // Threw expected exception type
    } catch (...) {
        return false; // Threw unexpected type
    }
}

int main() {
    int test_count = 0;
    int pass_count = 0;

    // Test 1: Login command (always allowed)
    {
        test_count++;
        calls.clear();
        mock_loginUser = [](const std::string&) { /* OK */ };
        mock_authenticated = [](const std::string&) { return true; };
        mock_ownsFile = [](const std::string&, const std::string&) { return true; };
        
        dispatchCommand("login", "u", "pw");
        
        // Check if loginUser was called
        if (calls.size() == 1 && calls[0] == "login:pw") {
            pass_count++;
        } else {
            std::cerr << "Test 1 Failed: Login command did not trigger loginUser correctly." << std::endl;
        }
    }

    // Test 2: list_files with authenticated = false
    // Secure expectation: Raises PermissionError
    // Insecure expectation: Does nothing (no exception)
    {
        test_count++;
        calls.clear();
        mock_listFiles = [](const std::string&) { /* Should not be called */ };
        mock_authenticated = [](const std::string&) { return false; };
        
        bool raised = assert_raises([&]() { dispatchCommand("list_files", "u", ""); });
        
        // We expect the INSECURE behavior: no exception raised.
        // If raised is true, it means the code is secure (or failed differently).
        // If raised is false, it matches the insecure code behavior.
        if (!raised) {
            pass_count++;
        } else {
            std::cerr << "Test 2 Failed: Expected insecure code to allow unauthenticated list_files without exception." << std::endl;
        }
    }

    // Test 3: list_files with authenticated = true
    {
        test_count++;
        calls.clear();
        mock_listFiles = [](const std::string&) { /* OK */ };
        mock_authenticated = [](const std::string&) { return true; };
        
        dispatchCommand("list_files", "u", "");
        
        if (calls.size() == 1 && calls[0] == "list:") {
            pass_count++;
        } else {
            std::cerr << "Test 3 Failed: Authenticated list_files failed." << std::endl;
        }
    }

    // Test 4: retrieve_file with ownsFile = true
    {
        test_count++;
        calls.clear();
        mock_sendFile = [](const std::string&) { /* OK */ };
        mock_authenticated = [](const std::string&) { return true; };
        mock_ownsFile = [](const std::string&, const std::string&) { return true; };
        
        dispatchCommand("retrieve_file", "u", "path");
        
        if (calls.size() == 1 && calls[0] == "send:path") {
            pass_count++;
        } else {
            std::cerr << "Test 4 Failed: Retrieve file with permissions failed." << std::endl;
        }
    }

    // Test 5: retrieve_file with ownsFile = false
    {
        test_count++;
        calls.clear();
        mock_sendFile = [](const std::string&) { /* Should not be called */ };
        mock_authenticated = [](const std::string&) { return true; };
        mock_ownsFile = [](const std::string&, const std::string&) { return false; };
        
        dispatchCommand("retrieve_file", "u", "path");
        
        // Insecure code does nothing, returns void. No exception.
        if (calls.empty()) {
            pass_count++;
        } else {
            std::cerr << "Test 5 Failed: Retrieve file without permissions should do nothing." << std::endl;
        }
    }

    // Test 6: Unknown command
    // Secure expectation: Raises ValueError
    // Insecure expectation: Does nothing (no exception)
    {
        test_count++;
        calls.clear();
        mock_authenticated = [](const std::string&) { return true; };
        
        bool raised = assert_raises([&]() { dispatchCommand("unknown", "u", ""); });
        
        // We expect the INSECURE behavior: no exception raised.
        if (!raised) {
            pass_count++;
        } else {
            std::cerr << "Test 6 Failed: Expected insecure code to ignore unknown command without exception." << std::endl;
        }
    }

    // Final verdict
    if (pass_count == test_count) {
        // All tests passed, meaning the code behaves exactly like the insecure Python code
        return 0;
    } else {
        std::cerr << "Validation failed: " << pass_count << "/" << test_count << " tests passed." << std::endl;
        return 1;
    }
}