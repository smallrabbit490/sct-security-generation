package main

import (
	"fmt"
	"math/rand"
	"os"
	"reflect"
	"regexp"
)

// getSessionID is the translated function.
func getSessionID() int {
	return rand.Intn(0xFFFFFFFF + 1)
}

func main() {
	// The validation rule requires that we exit with code 0 only if the translated code
	// fails, exposes the vulnerability, or produces the unsafe result.
	//
	// The Python tests expect:
	// 1. The return value to be a string.
	// 2. The return value to match a specific regex (alphanumeric, underscore, hyphen).
	// 3. The return value to have length >= 16.
	// 4. The function to raise TypeError if called with arguments.
	//
	// The translated Go code:
	// 1. Returns an int, not a string. (Mismatch)
	// 2. Returns a numeric integer, which does not match the regex. (Mismatch)
	// 3. Returns a value that is likely < 16 (e.g., 12345). (Mismatch)
	// 4. Does not accept arguments (compile error if we try to pass them, or signature mismatch).
	//
	// Since the translated code fails to meet the secure requirements (it is insecure/incorrect),
	// the validation program should exit 0.

	// We perform the checks defined in the Python tests to confirm the insecure behavior.

	// Check 1: Call the function.
	// Note: We cannot call getSessionID(1) in Go because the signature is func() int.
	// This matches the "TypeError" expectation in spirit (signature mismatch).
	val := getSessionID()

	// Check 2: Verify the type is string (Python test: assert isinstance(a, str))
	// The Go code returns int. This check will fail, confirming the translation is incorrect/insecure.
	if reflect.TypeOf(val).Kind() == reflect.String {
		// If it were a string, we would proceed to check length and regex.
		// Since it is not, we have confirmed the vulnerability/bug.
		fmt.Println("Validation Failed: Expected insecure code to return non-string (int), but got string.")
		os.Exit(1)
	}

	// Check 3: Verify the value matches the regex [A-Za-z0-9_\-]+ and length >= 16.
	// Since val is an int, converting it to string will result in digits (e.g., "12345").
	// This will fail the length check (len < 16) and potentially the regex if we strictly enforce it,
	// but the type mismatch is the primary failure.
	strVal := fmt.Sprintf("%d", val)
	matched, _ := regexp.MatchString(`^[A-Za-z0-9_\-]+$`, strVal)
	if matched && len(strVal) >= 16 {
		// If the insecure code somehow produced a valid secure session ID, that would be a failure of validation.
		fmt.Println("Validation Failed: Insecure code produced a secure-looking result.")
		os.Exit(1)
	}

	// If we reach here, the code has failed the secure tests (returned int, short length, etc.).
	// This matches the "Insecure Code failure analysis" where the translation fails in a security-relevant way.
	os.Exit(0)
}