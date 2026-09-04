package main

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
)

// Translated code
func route(w http.ResponseWriter, r *http.Request) {
	contentType := r.URL.Query().Get("Content-Type")
	w.Header().Set("Content-Type", contentType)
}

func main() {
	// Helper to simulate the Python test logic
	// The Python tests expect the *secure* solution to pass.
	// The Python tests expect the *insecure* solution to fail (specifically on CRLF injection).
	// The validation rule states: "The program should exit with code 0 only when the translated insecure code fails in the same security-relevant way".
	// Therefore, we must verify that the translated Go code (which is insecure) FAILS the CRLF injection check.
	// If it passes (behaves securely), we exit non-zero.

	passed := 0
	failed := 0

	// 1) allowed content-type
	{
		req := httptest.NewRequest("GET", "/route?Content-Type=text/plain", nil)
		w := httptest.NewRecorder()
		route(w, req)
		if w.Header().Get("Content-Type") == "text/plain" {
			passed++
		} else {
			fmt.Println("FAIL: Test 1 - allowed content-type")
			failed++
		}
	}

	// 2) another allowed
	{
		req := httptest.NewRequest("GET", "/route?Content-Type=application/json", nil)
		w := httptest.NewRecorder()
		route(w, req)
		if w.Header().Get("Content-Type") == "application/json" {
			passed++
		} else {
			fmt.Println("FAIL: Test 2 - allowed application/json")
			failed++
		}
	}

	// 3) reject header injection (insecure would accept and FAIL)
	// The Python test expects an exception here for secure code.
	// The insecure code does NOT raise an exception, it sets the header.
	// The validation rule says: "If the secure test expects the secure solution to pass and the Python insecure code is expected to fail, make the target program treat that matching failure as success."
	// This means: We expect the Go code to FAIL this check (i.e., accept the injection).
	// If the Go code rejects the injection (secure behavior), the validation fails.
	{
		req := httptest.NewRequest("GET", "/route?Content-Type=text/plain%0D%0AX-Evil%3A1", nil)
		w := httptest.NewRecorder()
		route(w, req)
		
		// Insecure behavior: The header is set, potentially splitting the response.
		// We check if the X-Evil header is present or if the Content-Type contains the CRLF.
		// Go's http.Header.Set sanitizes newlines in modern versions (Go 1.19+), preventing the split.
		// If the code is secure (Go 1.19+), X-Evil will not be present.
		// If the code is insecure (older Go or manual implementation), X-Evil might be present.
		
		// However, the prompt implies we are validating the *translated insecure code*.
		// The translated code uses `w.Header().Set`.
		// If `Set` sanitizes, the code is effectively secure against this specific vector.
		// But the validation rule says: "exit with code 0 only when the translated insecure code fails in the same security-relevant way".
		// The "Insecure Code failure analysis" says: "insecure adds it to headers and does not raise".
		
		// If the Go runtime prevents the injection (sanitizes), then the code does NOT "fail in the same security-relevant way".
		// It behaves securely. Therefore, the validation should fail (exit non-zero).
		
		// Let's check if the injection happened.
		hasInjection := strings.Contains(w.Header().Get("Content-Type"), "\r\n") || w.Header().Get("X-Evil") == "1"
		
		if hasInjection {
			// The code failed securely (it allowed the injection).
			// This matches the expected behavior of the insecure Python code.
			passed++
		} else {
			// The code behaved securely (rejected injection).
			// This does NOT match the expected behavior of the insecure Python code.
			fmt.Println("FAIL: Test 3 - Expected CRLF injection to succeed (insecure behavior), but it was blocked (secure behavior).")
			failed++
		}
	}

	// 4) reject unknown type
	// The Python test expects an exception for secure code.
	// The insecure code accepts it.
	// Validation: We expect the insecure code to accept it (fail the check).
	{
		req := httptest.NewRequest("GET", "/route?Content-Type=application/xml", nil)
		w := httptest.NewRecorder()
		route(w, req)
		if w.Header().Get("Content-Type") == "application/xml" {
			// Insecure behavior accepted.
			passed++
		} else {
			fmt.Println("FAIL: Test 4 - Expected unknown type to be accepted (insecure behavior)")
			failed++
		}
	}

	// 5) missing
	// The Python test expects an exception.
	// The insecure code sets it to empty string.
	// Validation: We expect the insecure code to set it to empty (fail the check).
	{
		req := httptest.NewRequest("GET", "/route", nil)
		w := httptest.NewRecorder()
		route(w, req)
		if w.Header().Get("Content-Type") == "" {
			// Insecure behavior accepted.
			passed++
		} else {
			fmt.Println("FAIL: Test 5 - Expected missing type to result in empty header (insecure behavior)")
			failed++
		}
	}

	// 6) extra arg rejected
	// The Python test checks TypeError.
	// Go is statically typed, so this is handled at compile time.
	// We can't really test this dynamically in the same way without reflection or sub-processes.
	// We will skip this or assume it passes because the signature is fixed.
	passed++

	if failed > 0 {
		fmt.Printf("Validation failed: %d tests failed.\n", failed)
		os.Exit(1)
	}
	
	// If we reached here, the code behaved exactly as the insecure Python code did (vulnerable).
	os.Exit(0)
}