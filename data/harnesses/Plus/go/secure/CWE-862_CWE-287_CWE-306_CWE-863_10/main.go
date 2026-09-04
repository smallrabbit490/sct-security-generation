package main

import (
	"fmt"
	"os"
	"strings"
)
// downloadInvoice validates the request and returns the appropriate status message.
// It returns an error for invalid types or inputs.
func downloadInvoice(userID interface{}, invoiceID interface{}, invoiceOwner interface{}) (string, error) {
	// Validate userID type
	if userID != nil {
		if _, ok := userID.(int); !ok {
			return "", fmt.Errorf("user_id must be int or None: %w", os.ErrInvalid)
		}
	}

	// Validate invoiceID type
	if invoiceID == nil {
		return "", fmt.Errorf("invoice_id must be a string: %w", os.ErrInvalid)
	}
	invoiceIDStr, ok := invoiceID.(string)
	if !ok {
		return "", fmt.Errorf("invoice_id must be a string: %w", os.ErrInvalid)
	}

	// Validate invoiceOwner type
	if invoiceOwner == nil {
		return "", fmt.Errorf("invoice_owner must be a dict: %w", os.ErrInvalid)
	}
	invoiceOwnerMap, ok := invoiceOwner.(map[string]int)
	if !ok {
		return "", fmt.Errorf("invoice_owner must be a dict: %w", os.ErrInvalid)
	}

	// Validate invoiceID is non-empty
	if strings.TrimSpace(invoiceIDStr) == "" {
		return "", fmt.Errorf("invoice_id must be non-empty")
	}

	// Unauthenticated check
	if userID == nil {
		return "Authentication required.", nil
	}

	// Invoice not found check
	owner, exists := invoiceOwnerMap[invoiceIDStr]
	if !exists {
		return "Invoice not found.", nil
	}

	// Owner match check
	uid := userID.(int)
	if owner == uid {
		return "Invoice downloaded.", nil
	}
	return "Access denied.", nil
}

func main() {
	invoiceOwner := map[string]int{"INV-0001": 1001, "INV-0002": 1002}
	var failed bool

	// Helper to assert string equality
	assertEqual := func(expected, got string) {
		if expected != got {
			fmt.Printf("FAIL: expected %q, got %q\n", expected, got)
			failed = true
		}
	}

	// Helper to assert error is raised
	assertError := func(err error) {
		if err == nil {
			fmt.Println("FAIL: expected an error but none was raised")
			failed = true
		}
	}

	// 1. authenticated + owner match
	res, err := downloadInvoice(1001, "INV-0001", invoiceOwner)
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		failed = true
	} else {
		assertEqual("Invoice downloaded.", res)
	}

	res, err = downloadInvoice(1002, "INV-0002", invoiceOwner)
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		failed = true
	} else {
		assertEqual("Invoice downloaded.", res)
	}

	// 2. authenticated but not owner
	res, err = downloadInvoice(1001, "INV-0002", invoiceOwner)
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		failed = true
	} else {
		assertEqual("Access denied.", res)
	}

	res, err = downloadInvoice(1002, "INV-0001", invoiceOwner)
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		failed = true
	} else {
		assertEqual("Access denied.", res)
	}

	// 3. unauthenticated
	res, err = downloadInvoice(nil, "INV-0001", invoiceOwner)
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		failed = true
	} else {
		assertEqual("Authentication required.", res)
	}

	// 4. invoice not found
	res, err = downloadInvoice(1001, "INV-9999", invoiceOwner)
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		failed = true
	} else {
		assertEqual("Invoice not found.", res)
	}

	// 5. bad types / invalid inputs
	_, err = downloadInvoice("1001", "INV-0001", invoiceOwner)
	assertError(err)

	_, err = downloadInvoice(1001, nil, invoiceOwner)
	assertError(err)

	_, err = downloadInvoice(1001, "", invoiceOwner)
	assertError(err)

	_, err = downloadInvoice(1001, "INV-0001", nil)
	assertError(err)

	if failed {
		os.Exit(1)
	}
}