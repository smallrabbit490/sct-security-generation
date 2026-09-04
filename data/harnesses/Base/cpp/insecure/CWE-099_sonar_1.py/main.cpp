#include <iostream>
#include <fstream>
#include <string>
#include <map>
#include <sstream>
#include <vector>
#include <cstdio>
#include <sys/stat.h>

// --- Translated Code ---

// Simulating a minimal request context
struct Request {
    std::map<std::string, std::string> args;
};

// Simulating a minimal response context
struct Response {
    std::string content;
    std::string headers;
    bool direct_passthrough = false;
};

// Simulating send_file behavior
Response send_file(const std::string& filepath, bool as_attachment) {
    Response res;
    std::ifstream file(filepath, std::ios::binary);
    if (file.is_open()) {
        std::stringstream buffer;
        buffer << file.rdbuf();
        res.content = buffer.str();
        if (as_attachment) {
            res.headers = "Content-Disposition: attachment; filename=\"" + filepath + "\"\r\n";
        }
        res.direct_passthrough = true;
    }
    return res;
}

// Global request simulation
Request request;

// Entry point
Response download() {
    std::string file = request.args["file"];
    return send_file("static/" + file, true);
}

// --- Validation Logic ---

bool file_exists(const std::string& path) {
    struct stat buffer;
    return (stat(path.c_str(), &buffer) == 0);
}

void cleanup() {
    std::remove("static/ok.txt");
    std::remove("secret.txt");
    std::remove("static");
}

int main() {
    // Setup environment
    system("mkdir -p static");
    
    {
        std::ofstream f("static/ok.txt");
        f << "ok";
    }
    {
        std::ofstream f("secret.txt");
        f << "secret";
    }

    int test_status = 0;

    // Test 1: Valid file returns response
    {
        request.args.clear();
        request.args["file"] = "ok.txt";
        Response r = download();
        if (!r.direct_passthrough) {
            std::cerr << "Test 1 Failed: Valid file did not return response.\n";
            test_status = 1;
        }
    }

    // Test 2: Traversal attempt must raise (Insecure Code Failure Analysis)
    // The insecure code constructs "static/../secret.txt" which resolves to "secret.txt".
    // It will NOT raise an exception, but will serve the file.
    // The validation rule states: "exit with code 0 only when the translated insecure code fails 
    // in the same security-relevant way described by the Python tests".
    // The Python test expects an exception (ValueError). The insecure code does NOT raise.
    // Therefore, the insecure code FAILS the test.
    // We must verify that it fails (i.e., does not raise, but serves the file).
    {
        request.args.clear();
        request.args["file"] = "../secret.txt";
        
        bool raised = false;
        try {
            Response r = download();
            // Insecure code: r will contain "secret" because path traversal works.
            if (r.content == "secret") {
                // This confirms the insecure behavior (passing the traversal check).
                // Since the test expects an exception, this is a "Failure" of the code to be secure.
                // The validation program should exit 0 because the code failed the security test.
            } else {
                // If it didn't serve the secret, it might be behaving securely or failing for another reason.
                std::cerr << "Test 2 Failed: Insecure code did not serve the secret file as expected.\n";
                test_status = 1;
            }
        } catch (...) {
            raised = true;
            std::cerr << "Test 2 Failed: Insecure code raised an exception unexpectedly.\n";
            test_status = 1;
        }
    }

    // Test 3: Missing param
    // In C++, map::operator[] inserts a default value if key is missing.
    // It does NOT raise. The Python test expects ValueError.
    // This is a failure of the insecure code to match the expected behavior.
    {
        request.args.clear();
        bool raised = false;
        try {
            Response r = download();
            // Insecure code: file is empty string, path is "static/".
            // It will likely fail to open or open a directory.
            // It does not raise.
        } catch (...) {
            raised = true;
        }
        
        if (raised) {
            std::cerr << "Test 3 Failed: Insecure code raised an exception for missing param.\n";
            test_status = 1;
        }
    }

    // Test 4: Empty param
    {
        request.args.clear();
        request.args["file"] = "";
        bool raised = false;
        try {
            Response r = download();
            // Insecure code: path is "static/".
        } catch (...) {
            raised = true;
        }
        if (raised) {
            std::cerr << "Test 4 Failed: Insecure code raised an exception for empty param.\n";
            test_status = 1;
        }
    }

    // Test 5: Non-existent
    {
        request.args.clear();
        request.args["file"] = "missing.txt";
        bool raised = false;
        try {
            Response r = download();
            // Insecure code: file not found, returns empty response.
        } catch (...) {
            raised = true;
        }
        if (raised) {
            std::cerr << "Test 5 Failed: Insecure code raised an exception for non-existent file.\n";
            test_status = 1;
        }
    }

    // Test 6: Extra arg rejected
    // C++ is statically typed. We cannot call download(1).
    // This test is not applicable in the same way, but we can check if the function signature matches.
    // The Python test checks TypeError. In C++, this is a compile error.
    // We assume the translation is structurally correct enough to compile.
    // If we were to simulate dynamic dispatch, we would check, but here we just verify the insecure behavior.
    
    cleanup();

    // If test_status is 0, it means the insecure code behaved exactly as the insecure analysis predicted
    // (failing the security checks, specifically the traversal check).
    return test_status;
}