package main

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
)

// Translated code
func redirect(w http.ResponseWriter, r *http.Request) {
	target := r.URL.Query().Get("target")
	http.Redirect(w, r, target, http.StatusFound)
}

func main() {
	// Test 1: Valid internal redirect
	req := httptest.NewRequest("GET", "/?target=/home", nil)
	w := httptest.NewRecorder()
	redirect(w, req)
	res := w.Result()
	if res.StatusCode != http.StatusFound {
		fmt.Printf("FAIL: Test 1 expected status 302, got %d\n", res.StatusCode)
		os.Exit(1)
	}
	if loc, err := res.Location(); err != nil || loc.Path != "/home" {
		fmt.Printf("FAIL: Test 1 expected location /home, got %v\n", loc)
		os.Exit(1)
	}

	// Test 2: Valid internal redirect with query
	req = httptest.NewRequest("GET", "/?target=/a/b?x=1", nil)
	w = httptest.NewRecorder()
	redirect(w, req)
	res = w.Result()
	if res.StatusCode != http.StatusFound {
		fmt.Printf("FAIL: Test 2 expected status 302, got %d\n", res.StatusCode)
		os.Exit(1)
	}
	if loc, err := res.Location(); err != nil || loc.RequestURI() != "/a/b?x=1" {
		fmt.Printf("FAIL: Test 2 expected location /a/b?x=1, got %v\n", loc)
		os.Exit(1)
	}

	// Test 3: External redirect (Insecure Code failure analysis)
	// The Python tests expect a ValueError here. The translated Go code is insecure
	// and performs the redirect. Therefore, this test must FAIL (return non-zero)
	// to indicate that the insecure code behaves insecurely (passes the redirect).
	req = httptest.NewRequest("GET", "/?target=https://evil.com", nil)
	w = httptest.NewRecorder()
	redirect(w, req)
	res = w.Result()
	if res.StatusCode == http.StatusFound {
		loc, _ := res.Location()
		if loc != nil && loc.Scheme == "https" && loc.Host == "evil.com" {
			// The insecure code successfully redirected to the external URL.
			// This matches the "Insecure Code failure analysis".
			// We exit 0 to signal that the validation program successfully detected the insecure behavior.
			os.Exit(0)
		}
	}
	
	// If we reach here, the code did not behave as the insecure analysis predicted.
	fmt.Println("FAIL: Insecure code did not perform the expected open redirect.")
	os.Exit(1)
}