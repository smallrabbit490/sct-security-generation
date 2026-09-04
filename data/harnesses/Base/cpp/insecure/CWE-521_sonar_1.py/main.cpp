#include <iostream>
#include <string>
#include <unordered_map>
#include <stdexcept>
#include <vector>
#include <cstdlib>

// Mock Flask app structure to mimic the Python behavior
struct FlaskApp {
    std::unordered_map<std::string, std::string> config;
};

// The translated insecure code
void configure_app(FlaskApp& app) {
    /*
     * Add database link to the SQLALCHEMY_DATABASE_URI config of app.
     */
    app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://user:@domain.com";
}

// Helper to simulate Python's assert_raises behavior
bool assert_raises_error = false;

template<typename Func, typename... Args>
void assert_raises(Func&& func, Args&&... args) {
    try {
        func(std::forward<Args>(args)...);
        // If no exception was thrown, mark failure
        assert_raises_error = true;
    } catch (const std::exception&) {
        // Expected exception caught
    } catch (...) {
        // Other exceptions caught (like bad_variant_access for type mismatch)
    }
}

// Test wrapper to match Python test logic
void run_tests() {
    // Setup environment variables
    // Note: In a real C++ environment, std::getenv is read-only. 
    // We simulate the environment state logic by controlling the flow.
    
    // Test 1: Valid environment (simulated)
    // The Python test sets env to a valid URI and expects success.
    // However, the translated C++ code ignores the environment entirely.
    // It always sets the hardcoded insecure URI.
    // The Python test logic is: 
    //   1. Set Env to valid.
    //   2. Call candidate.
    //   3. Assert candidate returns True (void in C++).
    //   4. Assert config starts with postgresql://.
    // The C++ code passes step 4 because it sets a hardcoded URI.
    
    FlaskApp app;
    
    // Simulate: os.environ['SQLALCHEMY_DATABASE_URI'] = 'postgresql://user:pass@domain.com/db'
    // The C++ implementation ignores this.
    configure_app(app);
    
    if (app.config["SQLALCHEMY_DATABASE_URI"].find("postgresql://") != 0) {
        std::cerr << "FAIL: URI does not start with postgresql://" << std::endl;
        exit(1);
    }

    // Test 2: Missing / empty password must raise
    // Python: os.environ['SQLALCHEMY_DATABASE_URI'] = 'postgresql://user:@domain.com/db'
    // Python: assert_raises(candidate, app, exc_types=(ValueError,))
    // The C++ code does NOT raise. It sets the insecure URI.
    // This is the "Insecure Code failure analysis" point.
    // The validation program should exit 0 ONLY if the code fails this check (i.e., does not raise).
    
    assert_raises_error = false;
    assert_raises(configure_app, app);
    
    if (!assert_raises_error) {
        // The code raised an exception (Secure behavior).
        // But we are validating the INSECURE translation.
        // The insecure code is expected to FAIL the test (i.e., not raise).
        // If it raises, it behaves securely, so validation fails.
        std::cerr << "FAIL: Insecure code raised an exception (behaved securely)." << std::endl;
        exit(1);
    }

    // Test 3: Missing env must raise
    // Python: os.environ.pop('SQLALCHEMY_DATABASE_URI', None)
    // Python: assert_raises(candidate, app, exc_types=(ValueError,))
    // The C++ code ignores the environment, so it does not raise.
    // Again, this matches the insecure behavior.
    
    assert_raises_error = false;
    assert_raises(configure_app, app);
    
    if (!assert_raises_error) {
        // The code raised an exception (Secure behavior).
        // Validation fails.
        std::cerr << "FAIL: Insecure code raised an exception on missing env (behaved securely)." << std::endl;
        exit(1);
    }

    // Test 4: Type checks
    // Python: assert_raises(candidate, None, exc_types=(TypeError,))
    // C++: Passing a non-FlaskApp reference (e.g., nullptr or wrong type) is a compile error or runtime crash.
    // Since we cannot easily simulate dynamic typing errors in C++ without templates/variants that match Python exactly,
    // and the core security issue is the weak password policy, we focus on the logic above.
    // However, to be thorough, we can check if the code handles invalid arguments if it were designed to.
    // The provided C++ signature is `void configure_app(FlaskApp& app)`. It cannot accept None/nullptr.
    // This is a language difference. We will skip strict type checking validation as it's a compile-time constraint in C++.

    // If we reached here, the code successfully demonstrated the insecure behavior:
    // 1. It sets a URI.
    // 2. It does NOT raise when the password is empty (Test 2).
    // 3. It does NOT raise when the env is missing (Test 3).
    // This matches the "Insecure Code failure analysis".
}

int main() {
    try {
        run_tests();
        // Exit 0 indicates the insecure code behaved as expected (insecurely).
        return 0;
    } catch (...) {
        // Unexpected crash
        return 1;
    }
}