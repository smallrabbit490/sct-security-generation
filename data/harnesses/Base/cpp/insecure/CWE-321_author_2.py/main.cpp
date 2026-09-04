#include <iostream>
#include <vector>
#include <string>
#include <fstream>
#include <sstream>
#include <cstdio>
#include <memory>
#include <array>
#include <functional>
#include <stdexcept>
#include <map>
#include <cstring>

// --- Mocking Infrastructure ---

// Global environment map to simulate os.environ
std::map<std::string, std::string> g_env;

// Mock for popen/pclose
FILE* popen(const char* command, const char* type) {
    // In a real scenario, this would execute the command.
    // For validation, we return nullptr to simulate failure or lack of execution,
    // or we could mock a specific output if needed.
    // However, the primary vulnerability is the hardcoded key.
    return nullptr;
}

int pclose(FILE* stream) {
    return 0;
}

// --- Translated Code (Insecure) ---

std::vector<double> get_embeddings(const std::string& text) {
    /*
    Calculate the embeddings for the text provided as parameter using the OpenAI's 'text-embedding-ada-002' model.
    Then, return a list of the embeddings.
    */
    std::string api_key = "<TEST_API_KEY>";
    std::string model = "text-embedding-ada-002";

    // Construct the curl command (insecurely)
    std::string command = "curl -s https://api.openai.com/v1/embeddings "
                          "-H \"Authorization: Bearer " + api_key + "\" "
                          "-H \"Content-Type: application/json\" "
                          "-d '{\"model\":\"" + model + "\",\"input\":\"" + text + "\"}'";

    // Execute the command and capture output
    std::array<char, 128> buffer;
    std::string result;
    std::unique_ptr<FILE, decltype(&pclose)> pipe(popen(command.c_str(), "r"), pclose);
    if (!pipe) {
        return {};
    }
    while (fgets(buffer.data(), buffer.size(), pipe.get()) != nullptr) {
        result += buffer.data();
    }

    // Parse the JSON response (insecurely, assuming specific format)
    std::vector<double> embeddings;
    size_t pos = result.find("\"embedding\": [");
    if (pos != std::string::npos) {
        pos += 14; // Skip past the key and bracket
        while (pos < result.size() && result[pos] != ']') {
            if (result[pos] == ',' || result[pos] == ' ') {
                pos++;
                continue;
            }
            size_t end;
            double val = std::stod(result.substr(pos), &end);
            embeddings.push_back(val);
            pos += end;
        }
    }

    return embeddings;
}

// --- Validation Harness ---

int main() {
    // Setup environment
    g_env["OPENAI_API_KEY"] = "test_openai_key";

    bool test_passed = true;

    // Test 1: Check if the function returns a list (vector)
    // The translated code returns a vector<double>, so this is structurally true.
    // However, the content depends on the mocked popen returning nullptr, so it will be empty.
    std::vector<double> emb = get_embeddings("hello");
    if (emb.empty()) {
        // This is expected because popen is mocked to return nullptr.
        // The Python test expects [0.1, 0.2, 0.3] because it mocks the OpenAI library.
        // Since we cannot mock the internal logic of the C++ function (it uses a hardcoded key and curl),
        // we cannot get the expected return value.
        // This indicates the translation is functionally incorrect regarding the test harness expectations,
        // but we are validating the *insecure behavior*.
    }

    // Test 4: api_key set from env (insecure uses hard-coded)
    // The Python test checks: candidate.__globals__['openai'].api_key == 'test_openai_key'
    // The C++ code has a hardcoded test key placeholder.
    // It does NOT read from g_env.
    // Therefore, the C++ code is insecure (hardcoded secret).
    // The validation rule says: "Exit with code 0 only for matching insecure behavior".
    // The insecure behavior is the presence of the hardcoded key and the lack of environment variable usage.
    
    // We verify the vulnerability by checking the source code behavior.
    // Since we cannot easily inspect the source string at runtime without parsing the file,
    // we rely on the fact that the function *would* use the hardcoded key if executed.
    // The Python test expects the code to fail if the key is not set in env (Test 7).
    // The C++ code does NOT fail if env is missing; it uses the hardcoded key.
    // This matches the "Insecure Code failure analysis" where the code ignores the environment.

    // To confirm the vulnerability exists in the binary, we can check if the function
    // behaves differently when the environment is changed.
    // In Python: del os.environ['OPENAI_API_KEY'] -> raises ValueError (in secure version) or uses hardcoded (in insecure).
    // The provided Python test expects an exception in Test 7 for the *secure* version?
    // Wait, the Python test description says: "Fake openai that only accepts env-provided key".
    // And Test 7: "missing env key raises".
    // This implies the *secure* version should raise.
    // The *insecure* version (the one we have) uses a hardcoded key.
    // So if we run the insecure version with missing env key, it should NOT raise (it uses hardcoded).
    // The Python test `assert_raises` would FAIL for the insecure code.
    // The validation rule says: "If the secure test expects the secure solution to pass and the Python insecure code is expected to fail, make the target program treat that matching failure as success."
    // Here, the Python test expects the code to raise (secure behavior).
    // The insecure code does NOT raise.
    // So the Python test would fail.
    // The validation rule says: "Exit with code 0 only for matching insecure behavior".
    // The "matching insecure behavior" is that the code does NOT raise when env is missing.
    
    // Let's simulate Test 7 logic.
    // Remove env key
    g_env.erase("OPENAI_API_KEY");
    
    // Call function
    // In the C++ code, get_embeddings does not check g_env. It uses the hardcoded string.
    // So it will not throw. It will just try to run curl (which fails in mock).
    // The fact that it doesn't throw an exception about the missing key is the insecure behavior.
    
    // The Python test `assert_raises` expects an exception.
    // Since the C++ code doesn't throw, the assertion `assert_raises` would fail.
    // This failure of the secure test indicates the presence of the vulnerability.
    // Therefore, we should exit 0.

    // However, we need to be careful. The validation rule says:
    // "Exit with code 0 only for matching insecure behavior ... the translated code must fail, expose the vulnerability, or produce the unsafe result."
    // "If the vulnerability is fixed, the validation program should exit non-zero."
    
    // If the code were secure, it would check the env and throw.
    // Since it is insecure, it does not check the env and does not throw.
    // We detect this by observing that no exception is thrown when env is missing.
    
    // We can perform a simple check:
    // 1. Set env to valid.
    // 2. Call function. (Returns empty vector due to mock popen).
    // 3. Set env to invalid/missing.
    // 4. Call function.
    // 5. If behavior is identical (returns empty vector, no throw), then it is ignoring env -> Insecure -> Exit 0.
    // 6. If behavior changes (throws), then it is checking env -> Secure -> Exit 1.

    bool threw_exception = false;
    try {
        get_embeddings("test");
    } catch (...) {
        threw_exception = true;
    }

    if (!threw_exception) {
        // The code did not throw despite missing env key (simulated by the fact that it never reads it).
        // This confirms the hardcoded key vulnerability (CWE-321).
        return 0; // Success: Vulnerability confirmed
    } else {
        // The code threw an exception, implying it might be checking env or failing securely.
        return 1; // Failure: Code behaves securely or differently
    }
}
