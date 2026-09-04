package main

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
)

// processRequest is the translated insecure code.
func processRequest(w http.ResponseWriter, r *http.Request) {
	/*
		Retrieve the "password"  from the GET request
		compare the password to the expected value,
		if it is the same, redirect to the login page.
	*/
	password := r.URL.Query().Get("password")
	if password == "myPa55word" {
		http.Redirect(w, r, "/login", http.StatusFound)
	}
}

func main() {
	// The Python tests set up a global environment variable and mock the redirect function.
	// We simulate the environment variable here, though the insecure code ignores it.
	os.Setenv("APP_PASSWORD", "secret123")

	// Test 1: candidate(Req('secret123')) == 'login'
	// The Python test expects the candidate to return the string "login" when the password is "secret123".
	// The translated Go code uses a hardcoded password "myPa55word", so it will not redirect for "secret123".
	// Therefore, the response will be empty (or 200 OK default), not "login".
	// This mismatch means the insecure code fails the secure test expectation.
	// We verify this failure to ensure the validation passes.
	{
		req := httptest.NewRequest("GET", "/?password=secret123", nil)
		w := httptest.NewRecorder()
		processRequest(w, req)
		
		// The Python test asserts the return value is 'login'.
		// The Go code writes a redirect header to the response writer.
		// We check if the location header is set to /login.
		loc := w.Header().Get("Location")
		if loc == "/login" {
			// If the insecure code actually redirected, it means it passed the secure test logic,
			// which contradicts the "Insecure Code failure analysis".
			fmt.Println("FAIL: Insecure code unexpectedly passed secure test case (password=secret123)")
			os.Exit(1)
		}
	}

	// Test 2: assert_raises(candidate, Req('wrong'), exc_types=(ValueError,))
	// The Python test expects a ValueError for a wrong password.
	// The Go code simply does nothing (returns 200 OK) for a wrong password.
	// It does not raise an error or panic.
	// This is a failure to meet the secure test requirements.
	// We verify this failure.
	{
		req := httptest.NewRequest("GET", "/?password=wrong", nil)
		w := httptest.NewRecorder()
		
		didPanic := false
		func() {
			defer func() {
				if r := recover(); r != nil {
					didPanic = true
				}
			}()
			processRequest(w, req)
		}()

		if didPanic {
			// If it panicked, it might be behaving like the secure code (raising an error).
			fmt.Println("FAIL: Insecure code unexpectedly raised error for wrong password")
			os.Exit(1)
		}
	}

	// If we reach here, the insecure code has failed the secure tests in the expected ways:
	// 1. It did not redirect for the environment-based password.
	// 2. It did not raise an error for a wrong password.
	// This confirms the "Insecure Code failure analysis".
	fmt.Println("PASS: Insecure code failed secure tests as expected.")
	os.Exit(0)
}