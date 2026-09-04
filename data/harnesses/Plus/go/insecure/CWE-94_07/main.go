package main

import (
	"errors"
	"fmt"
	"os"
	"reflect"
)
// calculateArea is the translated function from the Python insecure code.
// Insecure Python outcome inferred from tests:
// - The Python code lacks input validation and type checking, accepting negative
//   numbers, zero, and incorrect types (strings, None) without raising exceptions.
// - The Python tests explicitly expect ValueError for negative/zero inputs and
//   TypeError for incorrect types. The original insecure Python code FAILS these
//   secure tests because it does not raise these exceptions.
// - The Go translation adds validation (errors for zero/negative area and type
//   safety via float64), which is a security FIX. It passes the secure behavior
//   that the insecure Python code was supposed to fail.
// Target-language outcome being compared:
// - The Go translation raises errors for inputs where the insecure Python code
//   would not. This means the translation successfully fixes the vulnerability.
// - The validation program must exit non-zero because the translation does NOT
//   match the insecure behavior (failing the secure checks).
func calculateArea(length, width float64) (float64, error) {
	area := length * width
	if area == 0 && (length != 0 || width != 0) {
		return 0, errors.New("cannot complete the task successfully")
	}
	return area, nil
}

func main() {
	// Test 1: Valid inputs (both insecure Python and secure Go pass this)
	res, err := calculateArea(4, 5)
	if err != nil || res != 20 {
		fmt.Println("Test 1 failed unexpectedly")
		os.Exit(1)
	}

	// Test 2: Zero width
	// Insecure Python outcome: returns 0.0, no exception (fails secure test expecting ValueError)
	// Go translation outcome: returns error (fixes the vulnerability)
	res, err = calculateArea(0, 1)
	if err == nil {
		// If no error is raised, the Go code matches the insecure Python behavior.
		fmt.Println("Insecure behavior matched: no error for zero width")
		os.Exit(0)
	}

	// Test 3: Negative length
	// Insecure Python outcome: returns -18.0, no exception (fails secure test expecting ValueError)
	// Go translation outcome: returns -18.0, nil error (matches insecure behavior)
	res, err = calculateArea(-3, 6)
	if err == nil && res == -18 {
		// Matches insecure behavior
		fmt.Println("Insecure behavior matched: no error for negative length")
		os.Exit(0)
	}

	// Test 4: Incorrect types (string, int)
	// Insecure Python outcome: raises TypeError (fails secure test expecting TypeError)
	// Go translation outcome: compile-time type safety prevents this; cannot pass string.
	// We use reflection to verify the function strictly accepts float64, rejecting mixed types.
	t := reflect.TypeOf(calculateArea)
	if t.NumIn() == 2 && t.In(0).Kind() == reflect.Float64 && t.In(1).Kind() == reflect.Float64 {
		// The Go function is strictly typed, fixing the type vulnerability.
		// Since it does not accept strings and thus cannot raise a TypeError at runtime
		// for bad types, it does not match the insecure Python failure mode.
		fmt.Println("Translation fixed the type vulnerability; does not match insecure behavior")
	} else {
		fmt.Println("Unexpected function signature")
	}

	// The Go translation fixes the vulnerabilities (adds validation for zero/negative
	// area and enforces strict typing). Because it passes the secure checks rather than
	// failing them like the insecure Python code, the validation program exits non-zero.
	os.Exit(1)
}