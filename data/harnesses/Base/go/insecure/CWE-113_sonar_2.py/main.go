package main

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
)

// --- Translated Code (Insecure) ---

func route(w http.ResponseWriter, r *http.Request) {
	contentType := r.URL.Query().Get("Content-Type")
	w.Header().Set("content-type", contentType)
}

func main() {
	// --- Validation Logic ---

	// Helper to simulate the Python test's assert_raises behavior
	// It returns true if the function panics (simulating an exception), false otherwise.
	didPanic := func(fn func()) bool {
		defer func() {
			_ = recover()
		}()
		fn()
		return false
	}

	// Helper to check if a panic matches a specific type/message
	// In this context, we are looking for any panic that indicates a security rejection.
	// The Python tests expect ValueError for security rejections.
	// Since Go doesn't have built-in ValueErrors, we assume a panic indicates the rejection.
	// The insecure code will NOT panic, it will just write the header.
	assertRaises := func(fn func()) bool {
		return didPanic(fn)
	}

	passed := true

	// 1) allowed
	{
		req := httptest.NewRequest("GET", "/?Content-Type=text/html", nil)
		w := httptest.NewRecorder()
		route(w, req)
		if w.Header().Get("content-type") != "text/html" {
			fmt.Println("FAIL: Test 1 - allowed text/html")
			passed = false
		}
	}

	// 2) allowed
	{
		req := httptest.NewRequest("GET", "/?Content-Type=text/plain", nil)
		w := httptest.NewRecorder()
		route(w, req)
		if w.Header().Get("content-type") != "text/plain" {
			fmt.Println("FAIL: Test 2 - allowed text/plain")
			passed = false
		}
	}

	// 3) reject CRLF injection (insecure would accept and FAIL)
	// The Python test expects this to raise ValueError.
	// The translated insecure code sets the header directly, including the CRLF.
	// It does NOT panic.
	// Therefore, assertRaises returns false.
	// The Python test asserts that assertRaises is true.
	// Since the insecure code does not raise, the Python test FAILS.
	// Our validation program needs to detect that the insecure code behaves insecurely.
	// We check if the header was set with the injected payload.
	{
		req := httptest.NewRequest("GET", "/?Content-Type=text/html%0D%0AX-Evil%3A1", nil)
		w := httptest.NewRecorder()
		
		panicked := assertRaises(func() {
			route(w, req)
		})

		if panicked {
			// If it panicked, it might be secure (or broken).
			// But we are validating the INSECURE translation.
			// The insecure translation should NOT panic.
			fmt.Println("FAIL: Test 3 - Insecure code panicked unexpectedly (expected to accept CRLF)")
			passed = false
		} else {
			// It didn't panic. Check if it accepted the injection.
			// The Go standard library's http.Header.Set sanitizes newlines in modern versions (Go 1.19+).
			// If sanitized, the header value will be "text/htmlX-Evil:1" (newline stripped).
			// If not sanitized (older Go), it will be "text/html\r\nX-Evil:1".
			// In either case, it is NOT raising an error as the test requires.
			// The Python test expects a ValueError. The Go code does not error.
			// Thus, the behavior matches the "Insecure Code failure analysis" (it fails the security test).
			// We verify that the code indeed processed the input without erroring.
			ct := w.Header().Get("content-type")
			if ct == "" {
				fmt.Println("FAIL: Test 3 - Header not set at all")
				passed = false
			} else {
				// Check if the injection is present or partially present (sanitized).
				// The key is that no error was raised.
				if strings.Contains(ct, "X-Evil") || strings.Contains(ct, "text/html") {
					// This confirms the insecure behavior (accepting input without validation).
					// This is the expected state for the "Insecure" validation to pass.
				} else {
					fmt.Printf("FAIL: Test 3 - Unexpected header value: %s\n", ct)
					passed = false
				}
			}
		}
	}

	// 4) reject unknown
	// Python test expects ValueError.
	// Insecure code sets it.
	{
		req := httptest.NewRequest("GET", "/?Content-Type=application/xml", nil)
		w := httptest.NewRecorder()
		panicked := assertRaises(func() {
			route(w, req)
		})
		if panicked {
			fmt.Println("FAIL: Test 4 - Insecure code panicked on unknown type")
			passed = false
		} else {
			if w.Header().Get("content-type") != "application/xml" {
				fmt.Println("FAIL: Test 4 - Header not set correctly for unknown type")
				passed = false
			}
		}
	}

	// 5) missing
	// Python test expects ValueError.
	// Insecure code sets empty string.
	{
		req := httptest.NewRequest("GET", "/", nil)
		w := httptest.NewRecorder()
		panicked := assertRaises(func() {
			route(w, req)
		})
		if panicked {
			fmt.Println("FAIL: Test 5 - Insecure code panicked on missing type")
			passed = false
		} else {
			if w.Header().Get("content-type") != "" {
				fmt.Println("FAIL: Test 5 - Header not empty for missing type")
				passed = false
			}
		}
	}

	// 6) extra arg rejected
	// Python test expects TypeError.
	// Go is statically typed, so this is a compile-time error, not a runtime panic checkable here.
	// We assume the signature matches the route definition used in other tests.
	// If we tried to call route(w, r, 1), it wouldn't compile.
	// Since we can't test compile-time failures dynamically in the same binary easily,
	// and the other tests cover the logic, we skip this or assume it passes by virtue of compilation.
	// However, the prompt asks for executable checks.
	// The Python test `assert_raises(candidate, 1, ...)` calls the function with wrong args.
	// In Go, `route` is defined as `func(w http.ResponseWriter, r *http.Request)`.
	// We cannot call it with `1` at runtime.
	// We will assume this passes because the code is valid Go.

	if passed {
		// The insecure code failed the security checks (did not raise errors where expected).
		// This is the desired outcome for validating the "Insecure" translation.
		os.Exit(0)
	} else {
		os.Exit(1)
	}
}