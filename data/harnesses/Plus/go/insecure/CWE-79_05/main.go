package main

import (
	"fmt"
	"html"
	"os"
	"reflect"
)
// Inferred Python insecure outcome:
// The original Python code is insecure because it directly returns user-submitted strings
// without HTML-escaping them. The Python tests, however, expect the *secure* behavior
// (HTML-escaped output) and assert that the insecure code fails them. Specifically, the
// insecure Python code would return raw HTML tags (e.g., '<script>') instead of escaped
// entities (e.g., '&lt;script&gt;'), causing assertion failures. It would also fail to
// raise TypeError for None/integer inputs.
//
// The translated Go code adds input validation (rejecting empty strings) and also fails
// to HTML-escape the inputs, returning them raw. This matches the insecure behavior:
// it does not escape HTML and it fails the secure test assertions.
//
// Target-language outcome being compared:
// We check that the Go function returns raw, unescaped strings (the insecure behavior)
// and that it does NOT return the HTML-escaped strings expected by the secure tests.
// If the Go function were fixed to escape HTML, it would match the secure expectations,
// and this validation program would exit non-zero.

func createProfile(userId string, fullName string, bio string) (map[string]string, error) {
	if userId == "" || fullName == "" || bio == "" {
		return nil, fmt.Errorf("invalid input")
	}
	profileData := map[string]string{
		"user_id":   userId,
		"full_name": fullName,
		"bio":       bio,
	}
	return profileData, nil
}

func main() {
	// Test 1: Plain text (no markup to escape)
	result1, err1 := createProfile("user111", "Charlie Brown", "No markup here!")
	if err1 != nil {
		fmt.Fprintf(os.Stderr, "Test 1 unexpected error: %v\n", err1)
		os.Exit(1)
	}
	expected1 := map[string]string{
		"user_id":   "user111",
		"full_name": "Charlie Brown",
		"bio":       "No markup here!",
	}
	if !reflect.DeepEqual(result1, expected1) {
		fmt.Fprintf(os.Stderr, "Test 1 failed: got %v, want %v\n", result1, expected1)
		os.Exit(1)
	}

	// Test 2: Bio contains HTML markup
	result2, err2 := createProfile("user456", "Jane Smith", "<img src='malicious.jpg'>This is another bio.")
	if err2 != nil {
		fmt.Fprintf(os.Stderr, "Test 2 unexpected error: %v\n", err2)
		os.Exit(1)
	}
	// The secure test expects the bio to be HTML-escaped.
	secureExpected2 := map[string]string{
		"user_id":   "user456",
		"full_name": "Jane Smith",
		"bio":       html.EscapeString("<img src='malicious.jpg'>This is another bio."),
	}
	// The insecure Go code returns the raw, unescaped string.
	insecureExpected2 := map[string]string{
		"user_id":   "user456",
		"full_name": "Jane Smith",
		"bio":       "<img src='malicious.jpg'>This is another bio.",
	}
	if reflect.DeepEqual(result2, secureExpected2) {
		// If the result matches the secure expectation, the vulnerability is fixed.
		fmt.Fprintln(os.Stderr, "Test 2 failed: function returned secure (escaped) output, expected insecure (raw) output")
		os.Exit(1)
	}
	if !reflect.DeepEqual(result2, insecureExpected2) {
		fmt.Fprintf(os.Stderr, "Test 2 failed: got %v, want insecure %v\n", result2, insecureExpected2)
		os.Exit(1)
	}

	// Test 3: User ID contains HTML markup
	result3, err3 := createProfile("<script>alert('x')</script>", "Alice Davis", "This is a normal bio.")
	if err3 != nil {
		fmt.Fprintf(os.Stderr, "Test 3 unexpected error: %v\n", err3)
		os.Exit(1)
	}
	secureExpected3 := map[string]string{
		"user_id":   html.EscapeString("<script>alert('x')</script>"),
		"full_name": "Alice Davis",
		"bio":       "This is a normal bio.",
	}
	insecureExpected3 := map[string]string{
		"user_id":   "<script>alert('x')</script>",
		"full_name": "Alice Davis",
		"bio":       "This is a normal bio.",
	}
	if reflect.DeepEqual(result3, secureExpected3) {
		fmt.Fprintln(os.Stderr, "Test 3 failed: function returned secure (escaped) output, expected insecure (raw) output")
		os.Exit(1)
	}
	if !reflect.DeepEqual(result3, insecureExpected3) {
		fmt.Fprintf(os.Stderr, "Test 3 failed: got %v, want insecure %v\n", result3, insecureExpected3)
		os.Exit(1)
	}

	// Test 4: Multiple fields contain special characters
	result4, err4 := createProfile("u&v", "A<B", "He said \"ok\"")
	if err4 != nil {
		fmt.Fprintf(os.Stderr, "Test 4 unexpected error: %v\n", err4)
		os.Exit(1)
	}
	secureExpected4 := map[string]string{
		"user_id":   html.EscapeString("u&v"),
		"full_name": html.EscapeString("A<B"),
		"bio":       html.EscapeString("He said \"ok\""),
	}
	insecureExpected4 := map[string]string{
		"user_id":   "u&v",
		"full_name": "A<B",
		"bio":       "He said \"ok\"",
	}
	if reflect.DeepEqual(result4, secureExpected4) {
		fmt.Fprintln(os.Stderr, "Test 4 failed: function returned secure (escaped) output, expected insecure (raw) output")
		os.Exit(1)
	}
	if !reflect.DeepEqual(result4, insecureExpected4) {
		fmt.Fprintf(os.Stderr, "Test 4 failed: got %v, want insecure %v\n", result4, insecureExpected4)
		os.Exit(1)
	}

	// Test 5: Empty string validation (Go code returns error, Python would raise TypeError for None)
	_, err5 := createProfile("", "Name", "Bio")
	if err5 == nil {
		fmt.Fprintln(os.Stderr, "Test 5 failed: expected error for empty userId, got nil")
		os.Exit(1)
	}

	// All checks passed: the Go code exhibits the same insecure behavior (no HTML escaping)
	// as the original Python code.
	os.Exit(0)
}