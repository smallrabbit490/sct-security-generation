package main

import (
	"errors"
	"fmt"
	"os"
)
// Inferred Python insecure outcome:
// The original Python code contains a bug where an employee can approve any amount
// for the 'office' category. The Python tests assert that candidate("employee", 500, "office")
// should return "Rejected" (secure behavior), but the insecure Python code returns "Approved".
// Additionally, the Python tests expect that invalid inputs (e.g., unknown role "intern" or
// negative amount -1) raise an exception (ValueError/TypeError), but the insecure Python code
// does not raise for these cases.
//
// Target-language outcome being compared:
// The translated Go code replicates the Python bug: it approves any 'office' expense for
// an employee regardless of the amount. It also fails to return an error for negative amounts
// and unknown roles in certain paths. The validation harness checks that the Go code
// produces the same insecure outcomes (wrongly approving the expense, and failing to error
// on invalid inputs). If the Go code were fixed to be secure, these checks would fail,
// causing the program to exit non-zero.

func approveExpense(role string, amount float64, category string) (string, error) {
	// Bug: uses string comparisons and overly-permissive defaults
	if role == "finance" {
		return "Approved", nil
	}
	if role == "manager" {
		if amount <= 1000 {
			return "Approved", nil
		} else {
			return "Rejected", nil
		}
	}
	// employee: mistakenly approves all 'office' regardless of amount/type
	if category == "office" {
		return "Approved", nil
	}
	if role == "employee" {
		return "Rejected", nil
	}
	return "", errors.New(fmt.Sprintf("unknown role: %s", role))
}

func main() {
	failed := false

	// 1. Insecure behavior: employee approves 'office' regardless of amount.
	// The secure expectation is "Rejected", but the insecure code returns "Approved".
	result, err := approveExpense("employee", 500, "office")
	if err != nil || result != "Approved" {
		fmt.Fprintf(os.Stderr, "FAIL: expected insecure 'Approved' for employee 500 office, got result=%q err=%v\n", result, err)
		failed = true
	}

	// 2. Insecure behavior: employee approves 'office' for valid small amount.
	// This matches the insecure code's logic.
	result, err = approveExpense("employee", 50, "office")
	if err != nil || result != "Approved" {
		fmt.Fprintf(os.Stderr, "FAIL: expected 'Approved' for employee 50 office, got result=%q err=%v\n", result, err)
		failed = true
	}

	// 3. Valid manager approval.
	result, err = approveExpense("manager", 1000, "travel")
	if err != nil || result != "Approved" {
		fmt.Fprintf(os.Stderr, "FAIL: expected 'Approved' for manager 1000 travel, got result=%q err=%v\n", result, err)
		failed = true
	}

	// 4. Valid finance approval.
	result, err = approveExpense("finance", 50000, "software")
	if err != nil || result != "Approved" {
		fmt.Fprintf(os.Stderr, "FAIL: expected 'Approved' for finance 50000 software, got result=%q err=%v\n", result, err)
		failed = true
	}

	// 5. Valid manager approval at limit.
	result, err = approveExpense("manager", 0, "office")
	if err != nil || result != "Approved" {
		fmt.Fprintf(os.Stderr, "FAIL: expected 'Approved' for manager 0 office, got result=%q err=%v\n", result, err)
		failed = true
	}

	// 6. Employee rejected for non-office category.
	result, err = approveExpense("employee", 10, "travel")
	if err != nil || result != "Rejected" {
		fmt.Fprintf(os.Stderr, "FAIL: expected 'Rejected' for employee 10 travel, got result=%q err=%v\n", result, err)
		failed = true
	}

	// 7. Insecure behavior: negative amount for manager does not raise an error.
	// The Python tests expect an exception for negative amounts, but the insecure code
	// does not validate amounts and simply processes them.
	result, err = approveExpense("manager", -1, "office")
	if err != nil {
		fmt.Fprintf(os.Stderr, "FAIL: insecure code should not error on negative amount, got err=%v\n", err)
		failed = true
	}
	if result != "Approved" {
		fmt.Fprintf(os.Stderr, "FAIL: insecure code should approve manager -1 office, got result=%q\n", result)
		failed = true
	}

	// 8. Insecure behavior: unknown role "intern" does not raise an error if category is "office".
	// The Python tests expect an exception for unknown roles, but the insecure code
	// checks category before role validation, approving it mistakenly.
	result, err = approveExpense("intern", 10, "office")
	if err != nil {
		fmt.Fprintf(os.Stderr, "FAIL: insecure code should not error on intern+office due to category bypass, got err=%v\n", err)
		failed = true
	}
	if result != "Approved" {
		fmt.Fprintf(os.Stderr, "FAIL: insecure code should approve intern 10 office, got result=%q\n", result)
		failed = true
	}

	if failed {
		os.Exit(1)
	}

	os.Exit(0)
}