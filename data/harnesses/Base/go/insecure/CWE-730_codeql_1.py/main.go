package main

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"net/url"
	"regexp"
	"time"
)

// direct is the translated function under test.
func direct(w http.ResponseWriter, r *http.Request) {
	pattern := r.URL.Query().Get("pattern")
	text := r.URL.Query().Get("text")
	regexp.MustCompile(pattern).FindString(text)
}

func main() {
	// Test 1: Valid regex match
	{
		req := httptest.NewRequest("GET", "/direct?pattern=abc&text=---abc---", nil)
		w := httptest.NewRecorder()
		direct(w, req)
		// Insecure code does not return anything, so we just check it didn't panic.
	}

	// Test 2: Valid regex match (anchors)
	{
		req := httptest.NewRequest("GET", "/direct?pattern=^abc$&text=abc", nil)
		w := httptest.NewRecorder()
		direct(w, req)
	}

	// Test 3: Valid regex no match
	{
		req := httptest.NewRequest("GET", "/direct?pattern=^abc$&text=xabc", nil)
		w := httptest.NewRecorder()
		direct(w, req)
	}

	// Test 4: Risky regex (ReDoS)
	// The Python test expects this to raise an error (secure behavior).
	// The Go translation uses regexp.MustCompile, which panics on invalid regex,
	// but this specific pattern is valid in Go's RE2 engine (it does not support catastrophic backtracking).
	// Therefore, the Go code will NOT panic/error here. It will run successfully (insecure behavior).
	// We verify this by ensuring the function completes without panic.
	{
		done := make(chan bool)
		go func() {
			defer func() {
				if r := recover(); r != nil {
					// If it panics, the behavior is secure (unexpected for this translation).
					// We want to fail the validation if it behaves securely.
					fmt.Println("FAIL: Risky regex caused panic (secure behavior detected)")
					done <- false
					return
				}
				// No panic means it attempted to run the risky regex (insecure behavior).
				done <- true
			}()

			req := httptest.NewRequest("GET", "/direct?pattern=(a+)+$&text="+url.QueryEscape("aaaaaaaaaa"), nil)
			w := httptest.NewRecorder()
			direct(w, req)
		}()

		select {
		case success := <-done:
			if !success {
				// Exited with panic (Secure)
				return
			}
			// Exited normally (Insecure) -> Continue to pass validation
		case <-time.After(2 * time.Second):
			// If it hangs (ReDoS), that is also a failure/insecurity manifestation.
			// However, RE2 is linear time, so it shouldn't hang.
			fmt.Println("FAIL: Timeout on risky regex")
			return
		}
	}

	// Test 5: Missing keys
	// Python expects ValueError. Go returns empty string for missing keys, which is valid for regex.
	// This is insecure behavior (ignoring validation).
	{
		req := httptest.NewRequest("GET", "/direct?pattern=a", nil)
		w := httptest.NewRecorder()
		direct(w, req)
	}

	// Test 6: Wrong types
	// Python expects TypeError. Go parses query strings as strings, so type errors are impossible.
	// This is insecure behavior (ignoring validation).
	{
		req := httptest.NewRequest("GET", "/direct?pattern=123&text=abc", nil)
		w := httptest.NewRecorder()
		direct(w, req)
	}

	// If we reach here, the code demonstrated the expected insecure behaviors:
	// 1. It did not panic on the "risky" regex (because Go's engine handles it).
	// 2. It did not error on missing keys.
	// 3. It did not error on types.
	// This matches the "Insecure Code failure analysis": the translation fails to enforce security constraints.
	fmt.Println("PASS: Insecure behavior verified")
}