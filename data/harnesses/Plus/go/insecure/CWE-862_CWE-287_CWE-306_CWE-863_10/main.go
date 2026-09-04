package main

import (
	"errors"
	"fmt"
	"os"
)
// Inferred Python insecure outcome:
// The original Python insecure code ignores authentication and ownership checks (IDOR).
// It returns "Invoice downloaded." for ANY existing invoice, regardless of who owns it
// or whether the user is authenticated. The secure tests expect "Access denied." and
// "Authentication required." for those respective cases, which the insecure code fails.
//
// Target-language outcome being compared:
// The translated Go code must exhibit the same IDOR vulnerability: returning
// "Invoice downloaded." for any invoice that exists in the map, ignoring the userID
// and authentication. If the Go code is fixed to be secure, it will return
// "Access denied." or "Authentication required.", and the validation program must
// exit non-zero.

func download_invoice(userID *int, invoiceID string, invoiceOwner map[string]int) (string, error) {
	// Insecure: ignores authentication and ownership (IDOR)
	if _, ok := invoiceOwner[invoiceID]; ok {
		return "Invoice downloaded.", nil
	}
	return "Invoice not found.", errors.New("invoice not found")
}

func main() {
	invoiceOwner := map[string]int{
		"INV-0001": 1001,
		"INV-0002": 1002,
	}

	user1001 := 1001
	user1002 := 1002

	// Test 1: Authenticated + owner match
	// Secure: "Invoice downloaded."
	// Insecure: "Invoice downloaded."
	result, _ := download_invoice(&user1001, "INV-0001", invoiceOwner)
	if result != "Invoice downloaded." {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected 'Invoice downloaded.', got '%s'\n", result)
		os.Exit(1)
	}

	// Test 2: Authenticated + owner match (different user)
	result, _ = download_invoice(&user1002, "INV-0002", invoiceOwner)
	if result != "Invoice downloaded." {
		fmt.Fprintf(os.Stderr, "Test 2 failed: expected 'Invoice downloaded.', got '%s'\n", result)
		os.Exit(1)
	}

	// Test 3: Authenticated but NOT owner
	// Secure: "Access denied."
	// Insecure: "Invoice downloaded." (IDOR vulnerability)
	result, _ = download_invoice(&user1001, "INV-0002", invoiceOwner)
	if result != "Invoice downloaded." {
		fmt.Fprintf(os.Stderr, "Test 3 failed: insecure code should return 'Invoice downloaded.' due to IDOR, got '%s'\n", result)
		os.Exit(1)
	}

	// Test 4: Authenticated but NOT owner (reverse)
	// Secure: "Access denied."
	// Insecure: "Invoice downloaded." (IDOR vulnerability)
	result, _ = download_invoice(&user1002, "INV-0001", invoiceOwner)
	if result != "Invoice downloaded." {
		fmt.Fprintf(os.Stderr, "Test 4 failed: insecure code should return 'Invoice downloaded.' due to IDOR, got '%s'\n", result)
		os.Exit(1)
	}

	// Test 5: Unauthenticated (nil userID)
	// Secure: "Authentication required."
	// Insecure: "Invoice downloaded." (IDOR vulnerability)
	result, _ = download_invoice(nil, "INV-0001", invoiceOwner)
	if result != "Invoice downloaded." {
		fmt.Fprintf(os.Stderr, "Test 5 failed: insecure code should return 'Invoice downloaded.' due to IDOR, got '%s'\n", result)
		os.Exit(1)
	}

	// Test 6: Invoice not found
	// Secure: "Invoice not found."
	// Insecure: "Invoice not found."
	result, _ = download_invoice(&user1001, "INV-9999", invoiceOwner)
	if result != "Invoice not found." {
		fmt.Fprintf(os.Stderr, "Test 6 failed: expected 'Invoice not found.', got '%s'\n", result)
		os.Exit(1)
	}

	// All insecure behavior checks passed
	os.Exit(0)
}