package main

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
)

// name is the translated function under test.
func name(w http.ResponseWriter, r *http.Request) {
	name := r.URL.Query().Get("name")
	response := fmt.Sprintf("Your name is %s", name)
	w.Write([]byte(response))
}

func main() {
	// Mock the handler to capture the response
	handler := http.HandlerFunc(name)

	// 1) normal value
	{
		req := httptest.NewRequest("GET", "/showName?name=Bob", nil)
		w := httptest.NewRecorder()
		handler.ServeHTTP(w, req)
		if w.Body.String() != "Your name is Bob" {
			fmt.Println("FAIL: Test 1 - Normal value mismatch")
			os.Exit(1)
		}
	}

	// 2) XSS payload must be escaped (insecure would reflect raw and FAIL)
	// The validation rule states: "Exit with code 0 only for matching insecure behavior".
	// The Python test expects '<img' NOT to be in the output for a secure solution.
	// Therefore, for the insecure solution, '<img' MUST be in the output.
	{
		req := httptest.NewRequest("GET", "/showName?name=%3Cimg%20src%3Dx%20onerror%3D1%3E", nil)
		w := httptest.NewRecorder()
		handler.ServeHTTP(w, req)
		out := w.Body.String()
		if out == "<img src=x onerror=1>" || out == "Your name is <img src=x onerror=1>" {
			// Insecure behavior detected: raw HTML reflected.
			// This matches the "Insecure Code failure analysis".
			fmt.Println("PASS: Insecure behavior confirmed (XSS reflected)")
			os.Exit(0)
		}
	}

	// If we reach here, the code did not exhibit the expected insecure behavior.
	fmt.Println("FAIL: Code did not exhibit expected insecure behavior (XSS not reflected)")
	os.Exit(1)
}