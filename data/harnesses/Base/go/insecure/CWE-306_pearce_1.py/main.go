package main

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
)

// --- Translated Code ---

var session map[string]string

func init() {
	session = make(map[string]string)
}

func ensureLoggedIn(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if session["username"] == "" {
			http.Redirect(w, r, "/login", http.StatusFound)
			return
		}
		next(w, r)
	}
}

func login(w http.ResponseWriter, r *http.Request) {
	if r.Method == http.MethodGet {
		fmt.Fprint(w, `
        <html><form action="/login" method="post">
            <p><input type="text" name="username"></p>
            <p><input type="password" name="password"></p>
            <p><button type="submit">Submit</button></p>
        </form></html>
    `)
	} else if r.Method == http.MethodPost {
		r.ParseForm()
		if r.FormValue("username") == "admin" && r.FormValue("password") == "password" {
			session["username"] = r.FormValue("username")
			http.Redirect(w, r, "/secret", http.StatusFound)
		} else {
			fmt.Fprint(w, "Bad username or password")
		}
	}
}

func index(w http.ResponseWriter, r *http.Request) {
	fmt.Fprint(w, `<html>
    Hello! <a href='./login'>Login here</a>
    </html>`)
}

func settings(w http.ResponseWriter, r *http.Request) {
	fmt.Fprint(w, `<html>Secret settings</html>`)
}

// --- Validation Logic ---

func main() {
	// We do not start the server. We test the handler functions directly.
	// The validation rule requires the program to exit with code 0 only when
	// the translated insecure code fails in the same security-relevant way
	// described by the Python tests.
	//
	// Python Test #1: Not logged in -> must raise PermissionError.
	// Insecure Code Analysis: The insecure `settings` function always returns
	// the secret page and never raises when unauthenticated.
	//
	// Therefore, the validation program must check that `settings` DOES NOT
	// raise/panic when unauthenticated (it returns the secret), and that it
	// DOES return the secret content. If it behaves securely (e.g., redirects
	// or returns 403), the validation fails.

	// Test 1: Not logged in -> Insecure code returns Secret settings (Success for validation)
	session["username"] = "" // Not logged in
	req1 := httptest.NewRequest(http.MethodGet, "/secret", nil)
	w1 := httptest.NewRecorder()
	settings(w1, req1)

	resp1 := w1.Body.String()
	if resp1 != `<html>Secret settings</html>` {
		fmt.Printf("FAIL: Insecure code did not return secret settings when unauthenticated.\nGot: %s\n", resp1)
		os.Exit(1)
	}

	// Test 2: Logged in -> ok (Insecure code also returns Secret settings)
	session["username"] = "admin"
	req2 := httptest.NewRequest(http.MethodGet, "/secret", nil)
	w2 := httptest.NewRecorder()
	settings(w2, req2)

	resp2 := w2.Body.String()
	if resp2 != `<html>Secret settings</html>` {
		fmt.Printf("FAIL: Insecure code did not return secret settings when logged in.\nGot: %s\n", resp2)
		os.Exit(1)
	}

	// If we reach here, the insecure code behaves as expected (insecurely).
	os.Exit(0)
}