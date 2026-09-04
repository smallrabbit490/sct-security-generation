#include <iostream>
#include <string>
#include <vector>
#include <sstream>
#include <cstdlib>
#include <memory>
#include <functional>
#include <stdexcept>
#include <cassert>

// --- Translated Code ---

class Payload {
public:
    // Simulate the __reduce__ method by returning a serialized representation
    // that includes the command to execute.
    std::string reduce() const {
        // In Python, __reduce__ returns (callable, args). Here we simulate that
        // by returning a string that represents the exec call with the command.
        return "exec:import os;os.system(\"ls\")";
    }
};

std::vector<char> makePickleData(const Payload& payload) {
    // Simulate pickle.dumps by serializing the payload object.
    // In this insecure example, we simply convert the reduce() output to bytes.
    std::string serialized = payload.reduce();
    return std::vector<char>(serialized.begin(), serialized.end());
}

// --- Validation Logic ---

// Helper to simulate Python's assert_raises
bool assert_raises(std::function<void()> func, bool expect_exception = true) {
    try {
        func();
        // If we reach here, no exception was thrown
        return !expect_exception;
    } catch (...) {
        // Exception was thrown
        return expect_exception;
    }
}

int main() {
    // The Python tests define a specific behavior for the 'candidate' (makePickleData).
    // The tests check if the candidate successfully serializes safe objects (dicts, lists)
    // and rejects unsafe objects (Payload, sets, raw bytes) by raising exceptions.
    
    // The Insecure Code failure analysis states:
    // "Insecure pickles Payload() successfully (no exception), but test requires TypeError for Payload(), so insecure fails."
    
    // Therefore, for the validation to pass (exit 0), the translated C++ code must
    // exhibit the insecure behavior: it must successfully process Payload() without
    // throwing an exception. If it throws an exception (secure behavior), the validation fails.

    // 1. Test Payload serialization
    Payload p;
    bool payload_raised = assert_raises([&p]() {
        makePickleData(p);
    }, true); // We expect an exception if it were secure

    if (payload_raised) {
        // The code raised an exception for Payload. This matches the SECURE expectation.
        // But we are validating the INSECURE translation.
        // The insecure code should NOT raise an exception here.
        // Since it did, the translation failed to replicate the insecurity.
        std::cerr << "Validation Failed: Code rejected Payload (Secure behavior detected)." << std::endl;
        return 1;
    }

    // 2. Verify that the code actually runs and produces output (simulating successful serialization)
    // If makePickleData crashes or throws for other reasons, that's also a failure of the specific insecure logic.
    try {
        auto data = makePickleData(p);
        if (data.empty()) {
             std::cerr << "Validation Failed: Payload serialization produced empty data." << std::endl;
             return 1;
        }
    } catch (...) {
        std::cerr << "Validation Failed: Unexpected exception during Payload serialization." << std::endl;
        return 1;
    }

    // If we reached here, Payload was serialized successfully without raising an exception.
    // This matches the "Insecure pickles Payload() successfully" description.
    // Thus, the validation passes.
    return 0;
}