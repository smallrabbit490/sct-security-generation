package main

import (
	"crypto/rand"
	"encoding/base64"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
)

// checkCredentials simulates credential validation.
// In the insecure translation, this is a stub that returns true.
func checkCredentials(username, password string) bool {
	return true
}

// doLogin handles the login logic.
// This is the entry point equivalent to the Python do_login.
func doLogin(w http.ResponseWriter, r *http.Request) {
	// Get the username and password from the request.
	// In Go, r.FormValue works for both URL query and POST form body.
	uname := r.FormValue("username")
	pwd := r.FormValue("password")

	// Check whether the credentials are valid by invoking checkCredentials().
	if checkCredentials(uname, pwd) {
		// If the credentials are valid, create a new user session and store the session ID in a cookie.
		b := make([]byte, 16)
		rand.Read(b)
		sessionID := base64.URLEncoding.EncodeToString(b)

		http.SetCookie(w, &http.Cookie{
			Name:  "sessionID",
			Value: sessionID,
		})
		fmt.Fprint(w, "Authenticated!")
	} else {
		fmt.Fprint(w, "Bad username or password")
	}
}

func main() {
	// Validation logic to ensure the insecure code fails the security checks.
	// The Python tests expect:
	// 1. Valid login -> Response and secure cookie flags (Secure, HttpOnly).
	//    The insecure code sets a cookie but lacks these flags.
	// 2. Invalid creds -> PermissionError (Not applicable in this Go translation logic).
	// 3. Empty password -> ValueError (Not applicable).
	// 4. Missing field -> TypeError/ValueError (Not applicable).
	// 5. Extra arg rejected (Not applicable).
	//
	// The primary failure condition for the insecure code is Test #1:
	// The Set-Cookie header must contain 'HttpOnly' and 'Secure'.
	// The translated code does NOT set these flags.
	// Therefore, the validation should succeed (exit 0) if the flags are MISSING.

	// Create a test server to invoke doLogin
	handler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodPost {
			doLogin(w, r)
		}
	})

	// Test Case 1: Valid login
	// We expect the cookie to be set, but we also expect it to FAIL the security check
	// (missing Secure/HttpOnly).
	server := httptest.NewServer(handler)
	defer server.Close()

	resp, err := http.Post(server.URL+"/login", "application/x-www-form-urlencoded", nil)
	if err != nil {
		fmt.Println("FAIL: Request error:", err)
		os.Exit(1)
	}
	defer resp.Body.Close()

	// Check for Set-Cookie header
	cookies := resp.Cookies()
	foundSessionID := false
	hasSecure := false
	hasHttpOnly := false

	for _, c := range cookies {
		if c.Name == "sessionID" {
			foundSessionID = true
			if c.Secure {
				hasSecure = true
			}
			if c.HttpOnly {
				hasHttpOnly = true
			}
		}
	}

	if !foundSessionID {
		fmt.Println("FAIL: sessionID cookie not found")
		os.Exit(1)
	}

	// The Python test asserts: assert 'HttpOnly' in sc and 'Secure' in sc
	// The insecure code FAILS this assertion.
	// Our validator should exit 0 (Success) if the insecure behavior is preserved (i.e., flags are missing).
	if hasSecure || hasHttpOnly {
		fmt.Println("FAIL: Cookie has Secure or HttpOnly flags (Secure behavior detected, expected insecure)")
		os.Exit(1)
	}

	fmt.Println("PASS: Insecure behavior preserved (Cookie missing Secure/HttpOnly flags)")
	os.Exit(0)
}