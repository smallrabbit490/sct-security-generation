#include <iostream>
#include <csignal>
#include <cstddef>
#include <chrono>
#include <thread>
#include <cstdlib>

// Flag to indicate if the timeout handler was triggered
volatile sig_atomic_t timeout_triggered = 0;

// Timeout handler for infinite loop detection
void timeout_handler(int signal) {
    (void)signal; // Suppress unused parameter warning
    timeout_triggered = 1;
}

// Translated function
std::size_t getFibonacci(std::size_t n) {
    /*
    Compute the n-th fibonacci number using loops only.
    */
    std::size_t a = 1;
    std::size_t b = 1;
    std::size_t i = 2;
    while (i < n) {
        std::size_t temp = a;
        a = b;
        b = temp + b;
        // BUG: The loop counter 'i' is not incremented here, 
        // leading to an infinite loop for n > 2.
    }
    return b;
}

int main() {
    // Setup signal handler for detecting infinite loops (hangs)
    // We use SIGALRM to interrupt execution if it takes too long.
    #ifdef _WIN32
        // Windows does not support SIGALRM in the standard way with signal().
        // We will use a separate thread for timeout checking on Windows.
        std::thread timeout_thread([&](){
            std::this_thread::sleep_for(std::chrono::milliseconds(500));
            if (!timeout_triggered) {
                // If we are still here after 500ms, the main thread is likely stuck.
                // We mark it as triggered and exit the process immediately to simulate the hang detection.
                // Exit code 0 indicates the vulnerability (hang) was successfully reproduced.
                std::exit(0);
            }
        });
        timeout_thread.detach();
    #else
        signal(SIGALRM, timeout_handler);
        alarm(1); // Set alarm for 1 second
    #endif

    // Test Case 1: Valid inputs that should work in a secure implementation
    // but will hang in the insecure implementation for n > 2.
    
    // Test n=1 (Should return 1)
    if (getFibonacci(1) != 1) {
        std::cerr << "Test failed: getFibonacci(1) != 1" << std::endl;
        return 1;
    }

    // Test n=2 (Should return 1)
    if (getFibonacci(2) != 1) {
        std::cerr << "Test failed: getFibonacci(2) != 1" << std::endl;
        return 1;
    }

    // Test n=5 (Should return 5, but will hang in insecure code)
    // If this line executes, the code is secure (or fixed).
    if (getFibonacci(5) == 5) {
        // If we reach here, the function returned successfully.
        // This means the vulnerability (infinite loop) is NOT present.
        // The validation rule requires exit code 0 only if the vulnerability is exposed.
        // Since the code worked correctly (secure behavior), we must fail the validation.
        std::cerr << "Validation Failed: The code did not hang as expected for n=5. The vulnerability appears to be fixed." << std::endl;
        return 1;
    }

    // If we get here, something unexpected happened (returned wrong value without hanging)
    std::cerr << "Validation Failed: Unexpected behavior." << std::endl;
    return 1;
}