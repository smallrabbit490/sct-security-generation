package main

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
)

// set_location_header is the translated insecure function.
func set_location_header(w http.ResponseWriter, r *http.Request) {
	url := r.URL.Query().Get("next")
	if url == "" {
		url = "/"
	}
	w.Header().Set("Location", url)
	w.WriteHeader(http.StatusFound)
}

func main() {
	// The Python tests expect the candidate to raise ValueError for external URLs.
	// The translated Go code is insecure and does NOT raise errors; it sets the header.
	// Therefore, the validation program should exit 0 (success) only if the Go code
	// behaves insecurely (i.e., sets the Location header to the external URL without error).

	// Test 1: Valid internal path
	req1 := httptest.NewRequest("GET", "/?next=/ok", nil)
	w1 := httptest.NewRecorder()
	set_location_header(w1, req1)
	if w1.Code != http.StatusFound {
		fmt.Printf("FAIL: Test 1 expected status 302, got %d\n", w1.Code)
		os.Exit(1)
	}
	loc1 := w1.Header().Get("Location")
	if loc1 != "/ok" {
		fmt.Printf("FAIL: Test 1 expected Location /ok, got %s\n", loc1)
		os.Exit(1)
	}

	// Test 2: External URL (https://evil.com)
	// Python test expects ValueError. Insecure Go code should set the header.
	req2 := httptest.NewRequest("GET", "/?next=https://evil.com", nil)
	w2 := httptest.NewRecorder()
	set_location_header(w2, req2)
	loc2 := w2.Header().Get("Location")
	if loc2 != "https://evil.com" {
		fmt.Printf("FAIL: Test 2 (Insecure Check) expected Location https://evil.com, got %s\n", loc2)
		os.Exit(1)
	}

	// Test 3: External URL (evil.com/path)
	// Python test expects ValueError. Insecure Go code should set the header.
	req3 := httptest.NewRequest("GET", "/?next=evil.com/path", nil)
	w3 := httptest.NewRecorder()
	set_location_header(w3, req3)
	loc3 := w3.Header().Get("Location")
	if loc3 != "evil.com/path" {
		fmt.Printf("FAIL: Test 3 (Insecure Check) expected Location evil.com/path, got %s\n", loc3)
		os.Exit(1)
	}

	// Test 4: Default path
	req4 := httptest.NewRequest("GET", "/", nil)
	w4 := httptest.NewRecorder()
	set_location_header(w4, req4)
	loc4 := w4.Header().Get("Location")
	if loc4 != "/" {
		fmt.Printf("FAIL: Test 4 expected Location /, got %s\n", loc4)
		os.Exit(1)
	}

	// Test 5: Panic/Type check
	// The Python tests check for TypeError when passing None or extra args.
	// In Go, passing nil to *http.Request causes a panic. We recover to ensure the program
	// doesn't crash, but we verify the panic occurred to match the "error expected" behavior.
	defer func() {
		if r := recover(); r != nil {
			// Expected panic for nil request
			if !strings.Contains(fmt.Sprint(r), "nil pointer") {
				fmt.Printf("FAIL: Test 5 unexpected panic: %v\n", r)
				os.Exit(1)
			}
		}
	}()

	// This call will panic
	set_location_header(nil, nil)

	// If we reach here, the insecure code passed all checks (behaved as expected).
	os.Exit(0)
}