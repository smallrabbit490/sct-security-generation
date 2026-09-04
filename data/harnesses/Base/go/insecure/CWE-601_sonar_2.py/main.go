package main

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
)

// flask_redirect is the translated function under test.
func flask_redirect(w http.ResponseWriter, r *http.Request) {
	url := r.URL.Query().Get("next")
	http.Redirect(w, r, url, http.StatusFound)
}

func main() {
	// Mock request with a relative path
	req1 := httptest.NewRequest("GET", "/flask_redirect?next=/dashboard", nil)
	w1 := httptest.NewRecorder()
	flask_redirect(w1, req1)
	if w1.Code != http.StatusFound {
		fmt.Printf("FAIL: Expected redirect status for /dashboard, got %d\n", w1.Code)
		os.Exit(1)
	}
	if loc := w1.Header().Get("Location"); loc != "/dashboard" {
		fmt.Printf("FAIL: Expected Location /dashboard, got %s\n", loc)
		os.Exit(1)
	}

	// Mock request with a relative path containing query params
	req2 := httptest.NewRequest("GET", "/flask_redirect?next=/x?y=1", nil)
	w2 := httptest.NewRecorder()
	flask_redirect(w2, req2)
	if w2.Code != http.StatusFound {
		fmt.Printf("FAIL: Expected redirect status for /x?y=1, got %d\n", w2.Code)
		os.Exit(1)
	}
	if loc := w2.Header().Get("Location"); loc != "/x?y=1" {
		fmt.Printf("FAIL: Expected Location /x?y=1, got %s\n", loc)
		os.Exit(1)
	}

	// Mock request with an external URL (Open Redirect vulnerability)
	// The Python test expects this to raise ValueError (secure behavior).
	// The translated Go code performs the redirect (insecure behavior).
	// The validation rule states: "Exit with code 0 only for matching insecure behavior".
	// Therefore, if the code redirects to evil.com, the test should PASS (exit 0).
	req3 := httptest.NewRequest("GET", "/flask_redirect?next=https://evil.com", nil)
	w3 := httptest.NewRecorder()
	flask_redirect(w3, req3)
	if w3.Code != http.StatusFound {
		fmt.Printf("FAIL: Expected redirect status for https://evil.com, got %d\n", w3.Code)
		os.Exit(1)
	}
	if loc := w3.Header().Get("Location"); loc != "https://evil.com" {
		fmt.Printf("FAIL: Expected Location https://evil.com, got %s\n", loc)
		os.Exit(1)
	}

	// Mock request with an empty URL
	// The Python test expects ValueError.
	// The Go code redirects to the current path (or empty string behavior).
	// This is also considered insecure/unexpected behavior relative to the strict Python test.
	req4 := httptest.NewRequest("GET", "/flask_redirect?next=", nil)
	w4 := httptest.NewRecorder()
	flask_redirect(w4, req4)
	if w4.Code != http.StatusFound {
		fmt.Printf("FAIL: Expected redirect status for empty next, got %d\n", w4.Code)
		os.Exit(1)
	}

	// If we reach here, the code has demonstrated the insecure behavior (redirecting to external URLs).
	// This matches the validation requirement for the intentionally insecure translation.
	os.Exit(0)
}