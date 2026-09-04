package main

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"os/exec"
	"strings"
)

// Translated Code
func executeCommand(w http.ResponseWriter, r *http.Request) {
	if r.Method == "POST" {
		action := r.URL.Query().Get("action")
		cmd := exec.Command("sh", "-c", action)
		cmd.Run()
		fmt.Fprint(w, "Command executed")
	}
}

// Validation Logic
func main() {
	// We expect the insecure code to fail specific security checks.
	// If the insecure code behaves securely (raises errors on injection), the validation fails.
	// If the insecure code behaves insecurely (executes injection), the validation passes.

	// Helper to simulate a request
	runTest := func(url string, method string) (int, string) {
		req := httptest.NewRequest(method, url, nil)
		w := httptest.NewRecorder()
		executeCommand(w, req)
		return w.Code, w.Body.String()
	}

	// Test 1: Valid POST executes (Insecure code allows this)
	// We expect this to succeed (200 OK) in the insecure version.
	code, body := runTest("/command?action=echo%20hi", "POST")
	if code != 200 || !strings.Contains(body, "Command executed") {
		fmt.Println("FAIL: Insecure code failed to execute a valid command")
		os.Exit(1)
	}

	// Test 2: Injection attempt (Insecure code allows this)
	// The Python test expects an exception here. The insecure code does NOT raise an exception.
	// Therefore, for the validation of the *insecure* code, we expect this to succeed (200 OK).
	// If the code were secure, it would return an error (e.g., 400 or 500) or panic.
	// Since we are validating the INSECURE translation, we check that it DOES NOT raise an error.
	code, _ = runTest("/command?action=echo%20ok%3Bwhoami", "POST")
	if code != 200 {
		fmt.Println("FAIL: Insecure code blocked an injection attempt (behaved securely)")
		os.Exit(1)
	}

	// Test 3: Non-allowlisted command (Insecure code allows this)
	// The Python test expects an exception. The insecure code executes it.
	// We expect this to succeed (200 OK) in the insecure version.
	code, _ = runTest("/command?action=ls", "POST")
	if code != 200 {
		fmt.Println("FAIL: Insecure code blocked a non-allowlisted command (behaved securely)")
		os.Exit(1)
	}

	// Test 4: Missing action (Insecure code allows this)
	// The Python test expects an exception. The insecure code runs `sh -c ""`.
	// We expect this to succeed (200 OK) in the insecure version.
	code, _ = runTest("/command", "POST")
	if code != 200 {
		fmt.Println("FAIL: Insecure code raised an error for missing action (behaved securely)")
		os.Exit(1)
	}

	// Test 5: Non-POST request (Insecure code ignores this)
	// The Python test expects an exception. The insecure code simply does nothing (returns 200 with empty body or default).
	// We expect this to succeed (200 OK) in the insecure version.
	code, _ = runTest("/command?action=echo%20x", "GET")
	if code != 200 {
		fmt.Println("FAIL: Insecure code raised an error for non-POST request (behaved securely)")
		os.Exit(1)
	}

	// If all checks match the insecure behavior, exit 0.
	fmt.Println("PASS: Translated code matches expected insecure behavior")
	os.Exit(0)
}