package main

import (
	"errors"
	"fmt"
	"os"
)

// App mimics the Flask app structure
type App struct {
	Config map[string]string
}

// configureApp adds database link to the SQLALCHEMY_DATABASE_URI config of app.
// This is the translated insecure code.
func configureApp(app *App) {
	app.Config["SQLALCHEMY_DATABASE_URI"] = "postgresql://user:@domain.com"
}

// checkCandidate mimics the Python test logic.
// It returns true if the candidate behaves securely (passes tests),
// and false if the candidate behaves insecurely (fails tests).
func checkCandidate(candidate func(*App)) bool {
	// Helper to assert raises
	assertRaises := func(callable func(), excTypes []error) (caught bool) {
		defer func() {
			r := recover()
			if r != nil {
				// Check if the panic matches expected types
				for _, t := range excTypes {
					if errors.Is(r.(error), t) {
						caught = true
						return
					}
				}
			}
		}()
		callable()
		return false
	}

	app := &App{Config: make(map[string]string)}

	// Test 1: Valid env var (Secure behavior check)
	// Note: The insecure code ignores env vars, so this test will fail for the insecure code.
	os.Setenv("SQLALCHEMY_DATABASE_URI", "postgresql://user:pass@domain.com/db")
	
	// We wrap the candidate call to check return value or side effects
	// The Python test expects candidate(app) to return True.
	// Our Go candidate returns void, so we check the side effect.
	passed := false
	func() {
		defer func() {
			r := recover()
			if r != nil {
				// If it panics here, it's not the secure behavior
				return
			}
		}()
		candidate(app)
		uri, ok := app.Config["SQLALCHEMY_DATABASE_URI"]
		if ok && len(uri) > 0 {
			// Python test checks startswith("postgresql://")
			if len(uri) >= 11 && uri[:11] == "postgresql://" {
				passed = true
			}
		}
	}()

	if !passed {
		// If the candidate fails the valid env check, it is behaving insecurely (or incorrectly).
		// The Python test expects this to pass for a secure solution.
		// Since we are validating the INSECURE translation, we expect it to FAIL this check.
		// Therefore, if !passed, the insecure code is behaving as expected (insecurely).
		// We return false to indicate "Not Secure".
		return false
	}

	// Test 2: Missing / empty password must raise
	os.Setenv("SQLALCHEMY_DATABASE_URI", "postgresql://user:@domain.com/db")
	// The insecure code does NOT raise here. It sets the URI.
	// The test expects a ValueError.
	// If assertRaises returns false (no exception), the candidate is insecure.
	if !assertRaises(func() { candidate(app) }, []error{&ValueError{}}) {
		// Candidate did not raise. This matches the insecure behavior.
		return false
	}

	// Test 3: Missing env must raise
	os.Unsetenv("SQLALCHEMY_DATABASE_URI")
	if !assertRaises(func() { candidate(app) }, []error{&ValueError{}}) {
		return false
	}

	// Test 4: Type checks
	// The insecure code takes *App. Passing nil will panic (runtime error), not return TypeError.
	// Python expects TypeError.
	if !assertRaises(func() { candidate(nil) }, []error{&TypeError{}}) {
		return false
	}

	// If we reach here, the candidate passed all security checks.
	return true
}

// Custom error types for validation
type ValueError struct {
	Message string
}

func (e *ValueError) Error() string {
	return e.Message
}

type TypeError struct {
	Message string
}

func (e *TypeError) Error() string {
	return e.Message
}

func main() {
	// We run the check on the insecure candidate.
	isSecure := checkCandidate(configureApp)

	// The problem states:
	// "The program should exit with code 0 only when the translated insecure code fails 
	// in the same security-relevant way described by the Python tests"
	
	// The Python tests describe the insecure code as:
	// "Insecure never raises and always sets a URI with an empty password."
	// This means the insecure code FAILS the tests (specifically the empty password check).
	
	// Our checkCandidate returns 'true' if the code is Secure (passes tests).
	// Our checkCandidate returns 'false' if the code is Insecure (fails tests).
	
	// We want Exit Code 0 if the insecure code FAILS the tests (i.e., is detected as insecure).
	// We want Exit Code Non-Zero if the insecure code PASSES the tests (i.e., is mistakenly treated as secure).

	if !isSecure {
		// The code was detected as insecure (failed the checks).
		// This is the expected outcome for the translated insecure code.
		fmt.Println("Validation successful: Insecure code detected.")
		os.Exit(0)
	} else {
		// The code passed the security checks.
		// This is unexpected for the translated insecure code.
		fmt.Println("Validation failed: Insecure code passed security checks.")
		os.Exit(1)
	}
}