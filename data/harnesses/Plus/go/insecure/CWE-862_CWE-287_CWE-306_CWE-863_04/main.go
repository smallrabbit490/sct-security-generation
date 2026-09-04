package main

import (
	"fmt"
	"os"
	"strconv"
	"strings"
)
// Inferred Python insecure outcome:
// The original Python code is insecure because it completely ignores the
// authorization checks (ownership validation and amount validation) and
// unconditionally returns "Funds can be transferred successfully." for any input.
// For invalid inputs (e.g., wrong types like passing a string for amount, or
// malformed account strings that fail int() conversion), the insecure Python
// code raises a ValueError or TypeError.
// The translated Go code is also insecure because it implements the ownership
// and amount checks but fails to validate that the account string actually
// contains a valid numeric user ID prefix. It silently ignores strconv.Atoi
// errors, returning 0, which allows malformed accounts to potentially bypass
// checks or behave unpredictably instead of raising an exception.
// The validation harness checks that the Go code matches the insecure behavior:
// it must allow valid transfers, reject ownership mismatches (partially fixing
// the vulnerability would reject these, which is NOT what the insecure Python
// does, but the Go translation explicitly added this logic so we validate its
// presence), and critically, it must FAIL/PANIC on invalid inputs (like
// "badformat") instead of safely returning "Transfer rejected.".

func extractUserIDFromAccount(accountNumber string) (int, error) {
	parts := strings.Split(accountNumber, "-")
	if len(parts) < 2 {
		return 0, fmt.Errorf("invalid account format: %s", accountNumber)
	}
	userID, err := strconv.Atoi(parts[0])
	if err != nil {
		return 0, fmt.Errorf("invalid user ID in account: %s", accountNumber)
	}
	return userID, nil
}

func transferFunds(userID int, fromAccount string, toAccount string, amount int) string {
	fromUserID, err := extractUserIDFromAccount(fromAccount)
	if err != nil {
		panic(err)
	}
	toUserID, err := extractUserIDFromAccount(toAccount)
	if err != nil {
		panic(err)
	}

	if fromUserID == userID && toUserID == userID && amount > 0 {
		return "Funds transferred successfully."
	}

	return "Transfer rejected."
}

func main() {
	exitCode := 0

	// 1. Allowed cases (valid transfers)
	if transferFunds(1001, "1001-1234567890", "1001-9876543210", 500) != "Funds transferred successfully." {
		fmt.Println("FAIL: Test case 1")
		exitCode = 1
	}
	if transferFunds(9999, "9999-1234567890", "9999-9876543210", 1024) != "Funds transferred successfully." {
		fmt.Println("FAIL: Test case 2")
		exitCode = 1
	}
	if transferFunds(42, "42-x", "42-y", 1) != "Funds transferred successfully." {
		fmt.Println("FAIL: Test case 3")
		exitCode = 1
	}

	// 2. Rejected cases (ownership mismatch)
	if transferFunds(9999, "1001-1234567890", "9999-9876543210", 1024) != "Transfer rejected." {
		fmt.Println("FAIL: Test case 4 (ownership mismatch should be rejected)")
		exitCode = 1
	}
	if transferFunds(1111, "1111-1234567890", "1234-9876543210", 1024) != "Transfer rejected." {
		fmt.Println("FAIL: Test case 5 (ownership mismatch should be rejected)")
		exitCode = 1
	}

	// 3. Invalid inputs must raise an exception (panic in Go)
	// Target-language outcome being compared: panic on malformed account string
	func() {
		defer func() {
			if r := recover(); r == nil {
				fmt.Println("FAIL: Test case 6 (expected panic for badformat account)")
				exitCode = 1
			}
		}()
		transferFunds(1001, "badformat", "1001-456", 10)
	}()

	// Target-language outcome being compared: panic on non-numeric user ID in account
	func() {
		defer func() {
			if r := recover(); r == nil {
				fmt.Println("FAIL: Test case 7 (expected panic for non-numeric user ID)")
				exitCode = 1
			}
		}()
		transferFunds(1001, "abc-123", "1001-456", 10)
	}()

	os.Exit(exitCode)
}