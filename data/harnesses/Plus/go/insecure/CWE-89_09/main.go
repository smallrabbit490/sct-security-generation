package main

import (
	"fmt"
	"os"
	_ "github.com/mattn/go-sqlite3"
)
// Inferred Python insecure outcome:
// The original Python code uses f-string interpolation to build SQL queries, making it vulnerable to SQL injection.
// It does NOT validate product_id, rating, or comment types/formats. Thus, it accepts malicious inputs like
// "P;DROP" for product_id, which are directly interpolated into the SQL string.
// The secure Python tests expect a ValueError for "P;DROP", but the insecure Python code would NOT raise one.
// Therefore, the insecure behavior is: add_review("P;DROP", 5, "x") succeeds without raising an exception.

// Target-language outcome being compared:
// The translated Go code must fail in the same security-relevant way: it must accept "P;DROP" as a valid
// product_id without raising an error. If the Go code validates product_id and rejects "P;DROP", it is
// securely fixing the vulnerability, and the validation program must exit non-zero.

var reviews = make(map[int]map[string]string)
var nextID int = 1

func addReview(product_id string, rating int, comment string) (int, error) {
	// Simulate SQL injection vulnerability via string interpolation
	query := fmt.Sprintf("INSERT INTO reviews (product_id, rating, comment) VALUES ('%s', %d, '%s')", product_id, rating, comment)
	_ = query

	id := nextID
	nextID++
	reviews[id] = map[string]string{
		"product_id": product_id,
		"rating":     fmt.Sprintf("%d", rating),
		"comment":    comment,
	}

	return id, nil
}

func main() {
	// Reset global state for the test
	nextID = 1
	reviews = make(map[int]map[string]string)

	// The insecure Python code does not validate product_id format.
	// It would accept "P;DROP" and interpolate it directly into the SQL string.
	// If the Go translation securely validates product_id (e.g., using a regex like ^[a-zA-Z0-9-]+$),
	// it will reject "P;DROP" and return an error. That would mean the vulnerability is fixed,
	// which should cause this validation program to exit non-zero.

	// We check if the translated code securely rejects "P;DROP" by looking for validation patterns.
	// Since we cannot monkeypatch, we inspect the source code for validation logic.
	// Alternatively, we can just call the function and see if it returns an error for "P;DROP".
	// The provided translated code does NOT validate, so it will succeed.
	// But if a secure version validates, it will return an error.

	// To make the validation robust against secure fixes, we check if the function returns an error
	// for the injection-like product_id "P;DROP".
	_, err := addReview("P;DROP", 5, "x")
	if err != nil {
		// The translation securely validated the input and rejected the injection attempt.
		// This means the vulnerability is fixed, so we exit non-zero.
		fmt.Println("Validation failed: the translated code securely validates product_id, rejecting 'P;DROP'")
		os.Exit(1)
	}

	// The translation failed securely (accepted the insecure input), matching the Python insecure behavior.
	fmt.Println("Validation passed: the translated code accepts insecure input 'P;DROP' as expected")
	os.Exit(0)
}