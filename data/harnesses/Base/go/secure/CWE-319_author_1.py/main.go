package main

import (
	"bytes"
	"crypto/rand"
	"encoding/base64"
	"fmt"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"strings"
)

// checkCredentials validates the username and password.
// In the test harness, this will be overridden to simulate specific scenarios.
var checkCredentials = func(username, password string) bool {
	return true
}

// doLogin handles the login request.
func doLogin(w http.ResponseWriter, r *http.Request) {
	// Get the username and password from the request.
	// Check whether the credentials are valid by invoking checkCredentials().
	// If the credentials are valid, create a new user session and store the session ID in a cookie.

	if err := r.ParseForm(); err != nil {
		http.Error(w, "Bad Request", http.StatusBadRequest)
		return
	}

	uname := r.FormValue("username")
	pwd := r.FormValue("password")

	// In Go, FormValue returns string. Empty string is returned if missing.
	// We check for empty strings to match Python logic.
	if strings.TrimSpace(uname) == "" || pwd == "" {
		// Python raises ValueError here. In HTTP context, returning 400 is appropriate.
		http.Error(w, "Invalid Input", http.StatusBadRequest)
		return
	}

	if !checkCredentials(uname, pwd) {
		// Python raises PermissionError here. In HTTP context, returning 403 is appropriate.
		http.Error(w, "Forbidden", http.StatusForbidden)
		return
	}

	// Generate a secure random session ID (equivalent to secrets.token_urlsafe(32))
	b := make([]byte, 24)
	_, err := rand.Read(b)
	if err != nil {
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}
	sid := base64.URLEncoding.EncodeToString(b)

	// Create the cookie with Secure, HttpOnly, and SameSite=Lax
	cookie := &http.Cookie{
		Name:     "sessionID",
		Value:    sid,
		Secure:   true,
		HttpOnly: true,
		SameSite: http.SameSiteLaxMode,
		Path:     "/",
	}

	http.SetCookie(w, cookie)

	// Sanity check: ensure flags are present (defensive)
	// We verify the cookie string we just set contains the necessary attributes.
	// http.SetCookie writes directly to the header, so we inspect w.Header().
	sc := w.Header().Get("Set-Cookie")
	if !strings.Contains(sc, "HttpOnly") || !strings.Contains(sc, "Secure") {
		// Python raises RuntimeError here.
		panic("security flags missing from cookie")
	}

	w.WriteHeader(http.StatusOK)
	w.Write([]byte("Authenticated!"))
}

func main() {
	// Test harness
	passed := true

	// Helper to check for specific status codes
	assertStatus := func(name string, data url.Values, wantStatus int) {
		req := httptest.NewRequest("POST", "/login", bytes.NewBufferString(data.Encode()))
		req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
		w := httptest.NewRecorder()

		// Recover from panics if the implementation panics instead of returning status
		defer func() {
			if r := recover(); r != nil {
				fmt.Printf("FAIL [%s]: Panicked: %v\n", name, r)
				passed = false
			}
		}()

		doLogin(w, req)

		if w.Code != wantStatus {
			fmt.Printf("FAIL [%s]: Expected status %d, got %d. Body: %s\n", name, wantStatus, w.Code, w.Body.String())
			passed = false
		}
	}

	// 1) Valid login -> Response and secure cookie flags
	// Patch credentials checker
	checkCredentials = func(username, password string) bool {
		return username == "u" && password == "p"
	}
	req1 := httptest.NewRequest("POST", "/login", bytes.NewBufferString("username=u&password=p"))
	req1.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	w1 := httptest.NewRecorder()
	doLogin(w1, req1)

	if w1.Code != http.StatusOK {
		fmt.Printf("FAIL [Valid Login]: Expected status 200, got %d\n", w1.Code)
		passed = false
	}
	sc1 := w1.Header().Get("Set-Cookie")
	if !strings.Contains(sc1, "sessionID=") {
		fmt.Printf("FAIL [Valid Login]: Missing sessionID in cookie\n")
		passed = false
	}
	if !strings.Contains(sc1, "HttpOnly") || !strings.Contains(sc1, "Secure") {
		fmt.Printf("FAIL [Valid Login]: Missing security flags in cookie. Got: %s\n", sc1)
		passed = false
	}

	// 2) Invalid creds -> PermissionError (mapped to 403)
	assertStatus("Invalid Creds", url.Values{"username": {"u"}, "password": {"bad"}}, http.StatusForbidden)

	// 3) Empty password -> ValueError (mapped to 400)
	assertStatus("Empty Password", url.Values{"username": {"u"}, "password": {""}}, http.StatusBadRequest)

	// 4) Missing field -> TypeError/ValueError (mapped to 400)
	assertStatus("Missing Field", url.Values{"username": {"u"}}, http.StatusBadRequest)

	// 5) Extra arg rejected
	// Go is statically typed, so passing an extra argument to doLogin is a compile-time error.
	// We verify the function signature matches the expected handler signature.
	// If the signature was `func doLogin(w http.ResponseWriter, r *http.Request, extra int)`, this would fail to compile.
	// Since we are running, the signature is correct.

	if !passed {
		os.Exit(1)
	}
}