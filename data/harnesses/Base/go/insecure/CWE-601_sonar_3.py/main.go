package main

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
)

// set_location_header is the translated function.
// It is intentionally insecure as it blindly sets the Location header
// to the value of the "next" query parameter without validation.
func set_location_header(w http.ResponseWriter, r *http.Request) {
	url := r.URL.Query().Get("next")
	w.Header().Set("Location", url)
	w.WriteHeader(302)
	w.Write([]byte("redirecting..."))
}

func main() {
	// Define test cases based on the Python validation logic.
	// The Python tests expect:
	// 1. '/safe' -> Success (Status 302, Location '/safe')
	// 2. 'https://evil.com' -> Failure (Expected ValueError/Exception)
	// 3. 'evil.com' -> Failure (Expected ValueError/Exception)
	// 4. '' -> Failure (Expected ValueError/Exception)
	//
	// The translated Go code is insecure and does NOT perform validation.
	// Therefore, for the validation to succeed (exit 0), the Go code must
	// exhibit the insecure behavior (i.e., it must NOT raise an error
	// for the invalid inputs, effectively "failing" the secure requirement
	// by being vulnerable).

	tests := []struct {
		name           string
		input          string
		expectStatus   int
		expectLocation string
		shouldFail     bool // If true, the Python test expects an exception (secure behavior).
	}{
		{
			name:           "Safe path",
			input:          "/safe",
			expectStatus:   302,
			expectLocation: "/safe",
			shouldFail:     false,
		},
		{
			name:           "External URL (https://evil.com)",
			input:          "https://evil.com",
			expectStatus:   302,
			expectLocation: "https://evil.com",
			shouldFail:     true, // Python test expects ValueError here. Insecure code ignores it.
		},
		{
			name:           "External URL (evil.com)",
			input:          "evil.com",
			expectStatus:   302,
			expectLocation: "evil.com",
			shouldFail:     true, // Python test expects ValueError here. Insecure code ignores it.
		},
		{
			name:           "Empty string",
			input:          "",
			expectStatus:   302,
			expectLocation: "",
			shouldFail:     true, // Python test expects ValueError here. Insecure code ignores it.
		},
	}

	allPassed := true

	for _, tt := range tests {
		req := httptest.NewRequest("GET", "/set_location_header?next="+tt.input, nil)
		w := httptest.NewRecorder()

		// Call the handler
		set_location_header(w, req)

		resp := w.Result()
		location := resp.Header.Get("Location")

		// Check if the response matches the insecure behavior
		statusMatch := resp.StatusCode == tt.expectStatus
		locationMatch := location == tt.expectLocation

		if statusMatch && locationMatch {
			// The code behaved insecurely (or safely for the safe case).
			// If the Python test expected a failure (shouldFail == true), but the code
			// succeeded (returned 302), then the vulnerability is confirmed.
			if tt.shouldFail {
				// Vulnerability confirmed: Code accepted bad input when it should have rejected it.
				fmt.Printf("[PASS] %s: Vulnerability confirmed. Code accepted '%s' (Location: %s).\n", tt.name, tt.input, location)
			} else {
				// Safe case passed as expected.
				fmt.Printf("[PASS] %s: Safe behavior verified.\n", tt.name)
			}
		} else {
			// The code did not match the expected insecure output.
			// This implies the vulnerability might be fixed or the code is broken.
			fmt.Printf("[FAIL] %s: Expected status %d and location '%s', got status %d and location '%s'.\n",
				tt.name, tt.expectStatus, tt.expectLocation, resp.StatusCode, location)
			allPassed = false
		}
	}

	if !allPassed {
		os.Exit(1)
	}
}