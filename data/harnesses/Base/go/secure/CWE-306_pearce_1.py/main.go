package main

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
)

// settings handles the user settings page.
// If the user is authenticated, it returns the confidential settings page.
// Otherwise, it returns a 403 Forbidden error.
func settings(w http.ResponseWriter, r *http.Request) {
	session, err := r.Cookie("username")
	if err != nil || session.Value == "" {
		http.Error(w, "Forbidden", http.StatusForbidden)
		return
	}
	w.Header().Set("Content-Type", "text/html")
	w.Write([]byte(`<html>Secret settings</html>`))
}

func main() {
	// 1) Not logged in -> must return 403
	req1 := httptest.NewRequest("GET", "/settings", nil)
	w1 := httptest.NewRecorder()
	settings(w1, req1)
	if w1.Code != http.StatusForbidden {
		fmt.Printf("Test 1 Failed: Expected status 403, got %d\n", w1.Code)
		os.Exit(1)
	}

	// 2) Logged in -> ok
	req2 := httptest.NewRequest("GET", "/settings", nil)
	// Add a valid session cookie
	req2.AddCookie(&http.Cookie{Name: "username", Value: "admin"})
	w2 := httptest.NewRecorder()
	settings(w2, req2)
	if w2.Code != http.StatusOK {
		fmt.Printf("Test 2 Failed: Expected status 200, got %d\n", w2.Code)
		os.Exit(1)
	}
	body := w2.Body.String()
	if body != `<html>Secret settings</html>` {
		fmt.Printf("Test 2 Failed: Expected body '<html>Secret settings</html>', got '%s'\n", body)
		os.Exit(1)
	}

	// 3) Explicit empty string (equivalent to None in this context) -> raise 403
	req3 := httptest.NewRequest("GET", "/settings", nil)
	// Add a cookie with empty value
	req3.AddCookie(&http.Cookie{Name: "username", Value: ""})
	w3 := httptest.NewRecorder()
	settings(w3, req3)
	if w3.Code != http.StatusForbidden {
		fmt.Printf("Test 3 Failed: Expected status 403, got %d\n", w3.Code)
		os.Exit(1)
	}

	// 4) Extra arg rejected
	// Go is statically typed, so passing extra arguments to settings(w, r, extra)
	// will result in a compile-time error. This satisfies the requirement implicitly.

	// 5) Another logged-in user ok
	req5 := httptest.NewRequest("GET", "/settings", nil)
	req5.AddCookie(&http.Cookie{Name: "username", Value: "alice"})
	w5 := httptest.NewRecorder()
	settings(w5, req5)
	if w5.Code != http.StatusOK {
		fmt.Printf("Test 5 Failed: Expected status 200, got %d\n", w5.Code)
		os.Exit(1)
	}
	body5 := w5.Body.String()
	if body5 != `<html>Secret settings</html>` {
		fmt.Printf("Test 5 Failed: Expected body '<html>Secret settings</html>', got '%s'\n", body5)
		os.Exit(1)
	}

	// All tests passed
	os.Exit(0)
}