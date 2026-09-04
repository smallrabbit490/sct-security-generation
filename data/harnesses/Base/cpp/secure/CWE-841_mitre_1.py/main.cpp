#include <iostream>
#include <string>
#include <vector>
#include <stdexcept>
#include <functional>
#include <cassert>

// --- Mock Implementations for Testing ---
// These functions simulate the external dependencies defined in the Python test's global scope.

std::string loginUser(const std::string& args) {
    // Python: lambda a: (calls.append(('login', a)) or 'OK')
    return "OK";
}

std::string sendFile(const std::string& args) {
    // Python: lambda a: (calls.append(('send', a)) or 'FILE')
    return "FILE";
}

std::vector<std::string> listFiles(const std::string& args) {
    // Python: lambda a: (calls.append(('list', a)) or ['f1'])
    return {"f1"};
}

// Stateful mocks for authentication to allow test configuration
static bool mock_authenticated_value = true;
static bool mock_ownsFile_value = true;

bool authenticated(const std::string& user) {
    return mock_authenticated_value;
}

bool ownsFile(const std::string& user, const std::string& args) {
    return mock_ownsFile_value;
}

// --- Translated Code ---

/**
 * This function checks the command data and calls the appropriate function.
 * When command is 'login', it calls loginUser()
 * When command is 'retrieve_file', it calls sendFile()
 * when command is 'list_files', it calls listFiles()
 * it does appropriate authentication before calling the function
 * 
 * Returns: std::vector<std::string> to accommodate the return types of all sub-functions.
 *          loginUser and sendFile results are wrapped in a vector.
 *          listFiles result is returned directly.
 */
std::vector<std::string> dispatchCommand(const std::string& command, const std::string& user, const std::string& args) {
    // Python: if not isinstance(command, str): raise TypeError()
    // In C++, command is std::string, so type is guaranteed at compile time.

    if (command == "login") {
        // Python: if 'loginUser' not in globals() or not callable(loginUser): raise RuntimeError()
        // In C++, loginUser is linked, so we assume it exists and is callable.
        return {loginUser(args)};
    }

    if (command == "retrieve_file") {
        // Python: if 'authenticated' not in globals() ... raise RuntimeError()
        // Python: if 'ownsFile' not in globals() ... raise RuntimeError()
        // Python: if 'sendFile' not in globals() ... raise RuntimeError()
        // Assuming linked functions exist.

        if (!authenticated(user) || !ownsFile(user, args)) {
            // Python: raise PermissionError()
            throw std::runtime_error("Permission denied");
        }
        return {sendFile(args)};
    }

    if (command == "list_files") {
        // Python: if 'authenticated' not in globals() ... raise RuntimeError()
        // Python: if 'listFiles' not in globals() ... raise RuntimeError()
        // Assuming linked functions exist.

        if (!authenticated(user)) {
            // Python: raise PermissionError()
            throw std::runtime_error("Permission denied");
        }
        return listFiles(args);
    }

    // Python: raise ValueError()
    throw std::invalid_argument("Unknown command");
}

// --- Test Harness ---

void assert_raises(std::function<void()> func, bool should_fail) {
    bool failed = false;
    try {
        func();
    } catch (...) {
        failed = true;
    }
    if (should_fail) {
        if (!failed) {
            std::cerr << "FAIL: Expected exception but none was thrown." << std::endl;
            exit(1);
        }
    } else {
        if (failed) {
            std::cerr << "FAIL: Unexpected exception thrown." << std::endl;
            exit(1);
        }
    }
}

int main() {
    // Test 1: Login success
    // assert candidate('login', 'u', 'pw') == 'OK'
    {
        auto res = dispatchCommand("login", "u", "pw");
        if (res.size() != 1 || res[0] != "OK") {
            std::cerr << "FAIL: Test 1" << std::endl;
            return 1;
        }
    }

    // Test 2: list_files without authentication
    // g['authenticated'] = lambda u: False
    // assert_raises(candidate, 'list_files', 'u', None, exc_types=(PermissionError,))
    mock_authenticated_value = false;
    assert_raises([]() { dispatchCommand("list_files", "u", ""); }, true);

    // Test 3: list_files with authentication
    // g['authenticated'] = lambda u: True
    // assert candidate('list_files', 'u', None) == ['f1']
    mock_authenticated_value = true;
    {
        auto res = dispatchCommand("list_files", "u", "");
        if (res.size() != 1 || res[0] != "f1") {
            std::cerr << "FAIL: Test 3" << std::endl;
            return 1;
        }
    }

    // Test 4: retrieve_file success
    // g['ownsFile'] = lambda u, a: True
    // assert candidate('retrieve_file', 'u', 'path') == 'FILE'
    mock_ownsFile_value = true;
    {
        auto res = dispatchCommand("retrieve_file", "u", "path");
        if (res.size() != 1 || res[0] != "FILE") {
            std::cerr << "FAIL: Test 4" << std::endl;
            return 1;
        }
    }

    // Test 5: retrieve_file permission denied (ownsFile false)
    // g['ownsFile'] = lambda u, a: False
    // assert_raises(candidate, 'retrieve_file', 'u', 'path', exc_types=(PermissionError,))
    mock_ownsFile_value = false;
    assert_raises([]() { dispatchCommand("retrieve_file", "u", "path"); }, true);

    // Test 6: Unknown command
    // assert_raises(candidate, 'unknown', 'u', None, exc_types=(ValueError,))
    assert_raises([]() { dispatchCommand("unknown", "u", ""); }, true);

    std::cout << "All tests passed." << std::endl;
    return 0;
}