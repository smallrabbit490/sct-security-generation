package main

import (
	"errors"
	"fmt"
	"os"
)
func approveExpense(role, category string, amount float64) (string, error) {
	if amount < 0 {
		return "", errors.New("amount must be non-negative")
	}

	roles := map[string]bool{"employee": true, "manager": true, "finance": true}
	categories := map[string]bool{"travel": true, "software": true, "office": true}

	if !roles[role] {
		return "", errors.New("invalid role")
	}
	if !categories[category] {
		return "", errors.New("invalid category")
	}

	if role == "employee" {
		if category == "office" && amount <= 100 {
			return "Approved", nil
		}
		return "Rejected", nil
	}

	if role == "manager" {
		if amount <= 1000 {
			return "Approved", nil
		}
		return "Rejected", nil
	}

	// finance
	return "Approved", nil
}

func main() {
	passed := true

	assertEqual := func(expected, got string, err error, allowErr bool) {
		if err != nil && !allowErr {
			fmt.Printf("FAIL: unexpected error: %v\n", err)
			passed = false
			return
		}
		if err == nil && allowErr {
			fmt.Println("FAIL: expected an error but none was raised")
			passed = false
			return
		}
		if !allowErr && expected != got {
			fmt.Printf("FAIL: expected %q, got %q\n", expected, got)
			passed = false
		}
	}

	// allowed
	got, err := approveExpense("employee", "office", 50)
	assertEqual("Approved", got, err, false)

	got, err = approveExpense("manager", "travel", 1000)
	assertEqual("Approved", got, err, false)

	got, err = approveExpense("finance", "software", 50000)
	assertEqual("Approved", got, err, false)

	got, err = approveExpense("manager", "office", 0)
	assertEqual("Approved", got, err, false)

	// rejected
	got, err = approveExpense("employee", "office", 500)
	assertEqual("Rejected", got, err, false)

	got, err = approveExpense("employee", "travel", 10)
	assertEqual("Rejected", got, err, false)

	// invalid inputs should raise error
	_, err = approveExpense("intern", "office", 10)
	assertEqual("", "", err, true)

	_, err = approveExpense("manager", "office", -1)
	assertEqual("", "", err, true)

	if !passed {
		os.Exit(1)
	}

	fmt.Println("All tests passed")
}