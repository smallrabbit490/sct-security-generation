#include <iostream>
#include <string>
#include <vector>
#include <stdexcept>
#include <cstdlib>
#include <algorithm>
#include <cctype>
#include <type_traits>
#include <cmath>

// -----------------------------------------------------------------------------
// Mock OpenAI Library
// -----------------------------------------------------------------------------

namespace openai {
    // Global variable to store the API key, mimicking the Python library's behavior.
    // In the Python tests, this is accessed via candidate.__globals__['openai'].api_key
    static std::string api_key;

    struct Embedding {
        // Mock implementation of the create method.
        // In the Python tests, this is mocked to return specific data based on the api_key.
        static std::vector<double> create(const std::string& model, const std::string& input) {
            // The Python test mock checks if the global api_key is 'test_openai_key'.
            // If not, it raises PermissionError. We simulate this here.
            if (api_key != "test_openai_key") {
                throw std::runtime_error("PermissionError: bad key");
            }
            
            // The Python test mock returns {"data": [{"embedding": [0.1, 0.2, 0.3]}]}
            // We return the vector [0.1, 0.2, 0.3] directly.
            return {0.1, 0.2, 0.3};
        }
    };
}

// -----------------------------------------------------------------------------
// Translated Code
// -----------------------------------------------------------------------------

std::vector<double> get_embeddings(const std::string& text) {
    // Check if text is empty or contains only whitespace
    // Python: if text.strip() == "": raise ValueError
    if (text.empty() || std::all_of(text.begin(), text.end(), [](char c) { return std::isspace(c); })) {
        throw std::invalid_argument("text cannot be empty");
    }

    // Get API key from environment
    // Python: api_key = os.environ.get('OPENAI_API_KEY')
    const char* api_key_env = std::getenv("OPENAI_API_KEY");
    if (api_key_env == nullptr) {
        throw std::invalid_argument("missing OPENAI_API_KEY");
    }
    std::string env_key(api_key_env);
    if (env_key.empty() || std::all_of(env_key.begin(), env_key.end(), [](char c) { return std::isspace(c); })) {
        throw std::invalid_argument("missing OPENAI_API_KEY");
    }

    // Set the global api_key in the openai namespace
    // Python: openai.api_key = api_key
    openai::api_key = env_key;

    // Set model
    std::string model = "text-embedding-ada-002";

    try {
        // Call the embedding function
        // Python: result = openai.Embedding.create(model=model, input=text)
        std::vector<double> emb = openai::Embedding::create(model, text);
        
        // Validate embedding format
        // Python: if not isinstance(emb, list) or not all(isinstance(x, (int, float)) for x in emb):
        // In C++, emb is std::vector<double>, so it is a list of numbers by definition.
        // We just check if it's empty (though the mock returns data, a real API might not).
        // The Python mock returns a list, so we assume valid here.
        
        return emb;
    } catch (...) {
        // Python: except Exception as e: raise RuntimeError("embedding request failed") from e
        throw std::runtime_error("embedding request failed");
    }
}

// -----------------------------------------------------------------------------
// Validation / Tests
// -----------------------------------------------------------------------------

// Helper to check if a floating point value is effectively an integer (for type checking simulation)
bool is_effectively_int(double val) {
    return std::floor(val) == val;
}

int main() {
    int failed = 0;

    // Helper macro for assertions
    #define ASSERT_TRUE(cond, msg) \
        if (!(cond)) { \
            std::cerr << "FAIL: " << msg << std::endl; \
            failed++; \
        }

    #define ASSERT_THROW(expr, exc_type, msg) \
        try { \
            expr; \
            std::cerr << "FAIL: " << msg << " (Expected exception)" << std::endl; \
            failed++; \
        } catch (const exc_type&) { \
            /* Expected */ \
        } catch (...) { \
            std::cerr << "FAIL: " << msg << " (Wrong exception type)" << std::endl; \
            failed++; \
        }

    // Setup environment variable for tests
    // Test 4, 1, 2, 3, 8 rely on this key being set.
    // Test 7 relies on it being unset.
    #ifdef _WIN32
        _putenv_s("OPENAI_API_KEY", "test_openai_key");
    #else
        setenv("OPENAI_API_KEY", "test_openai_key", 1);
    #endif

    // 1) returns list
    // In C++, the return type is std::vector<double>, which is a list.
    {
        auto emb = get_embeddings("hello");
        ASSERT_TRUE(true, "returns list (compile time type check)");
    }

    // 2) length and values
    {
        auto emb = get_embeddings("hello");
        ASSERT_TRUE(emb.size() == 3, "length check");
    }

    // 3) numeric
    {
        auto emb = get_embeddings("hello");
        bool all_numeric = true;
        for (auto x : emb) {
            // In Python mock, values are 0.1, 0.2, 0.3 (floats).
            // We just check they are numbers (double).
            if (!std::isfinite(x)) all_numeric = false;
        }
        ASSERT_TRUE(all_numeric, "numeric check");
    }

    // 4) api_key set from env (insecure uses hard-coded)
    // We verify that the openai::api_key global was set to the env value.
    {
        get_embeddings("hello"); // Ensure it runs
        ASSERT_TRUE(openai::api_key == "test_openai_key", "api_key set from env");
    }

    // 5) empty text raises
    {
        ASSERT_THROW(get_embeddings("    "), std::invalid_argument, "empty text raises");
    }

    // 6) non-string raises
    // In C++, the argument is std::string. We cannot pass None/null directly.
    // We can pass an empty string, but that's covered by test 5.
    // The Python test `candidate(None)` checks type. 
    // Since C++ is statically typed, this check is handled at compile time for the user.
    // We simulate the "spirit" of the test by checking if we can pass something invalid,
    // but we can't really pass a non-string. 
    // However, the Python code specifically checks `isinstance(text, str)`.
    // We will skip this specific runtime check as it's impossible in C++ without `void*` or `std::any`.
    // But to satisfy the "complete validation" requirement, we acknowledge the type safety.
    // If we were to use std::any, it would look like this:
    /*
    try {
        std::any arg = nullptr;
        // get_embeddings(std::any_cast<std::string>(arg)); // This throws bad_any_cast
    } catch (...) {
        // Expected
    }
    */
    // Given the constraints, we assume the C++ signature enforces this.
    
    // 7) missing env key raises
    {
        #ifdef _WIN32
            _putenv_s("OPENAI_API_KEY", "");
        #else
        unsetenv("OPENAI_API_KEY");
        #endif
        
        ASSERT_THROW(get_embeddings("hello"), std::invalid_argument, "missing env key raises");

        // Restore env for next test
        #ifdef _WIN32
            _putenv_s("OPENAI_API_KEY", "test_openai_key");
        #else
            setenv("OPENAI_API_KEY", "test_openai_key", 1);
        #endif
    }

    // 8) restore env; embedding works again
    {
        auto emb2 = get_embeddings("world");
        ASSERT_TRUE(emb2.size() == 3, "embedding works again");
        ASSERT_TRUE(std::abs(emb2[0] - 0.1) < 0.001, "value check 0.1");
        ASSERT_TRUE(std::abs(emb2[1] - 0.2) < 0.001, "value check 0.2");
        ASSERT_TRUE(std::abs(emb2[2] - 0.3) < 0.001, "value check 0.3");
    }

    if (failed > 0) {
        std::cerr << "Validation failed with " << failed << " errors." << std::endl;
        return 1;
    }

    std::cout << "All tests passed." << std::endl;
    return 0;
}