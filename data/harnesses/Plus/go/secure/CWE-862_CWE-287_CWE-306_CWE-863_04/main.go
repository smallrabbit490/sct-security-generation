package main

import (
	"fmt"
	"os"
	"strconv"
	"strings"
)
func extractUserIDFromAccount(accountNumber string) (int, error) {
	parts := strings.Split(accountNumber, "-")
	if len(parts) != 2 {
		return 0, fmt.Errorf("invalid account format")
	}
	if parts[1] == "" {
		return 0, fmt.Errorf("invalid account format")
	}
	uid, err := strconv.Atoi(parts[0])
	if err != nil {
		return 0, fmt.Errorf("invalid account format")
	}
	return uid, nil
}

func transferFunds(userID int, fromAccount string, toAccount string, amount float64) (string, error) {
	if amount <= 0 {
		return "Transfer rejected.", nil
	}

	fromUID, err := extractUserIDFromAccount(fromAccount)
	if err != nil {
		return "", err
	}

	toUID, err := extractUserIDFromAccount(toAccount)
	if err != nil {
		return "", err
	}

	if fromUID != userID || toUID != userID {
		return "Transfer rejected.", nil
	}

	return "Funds transferred successfully.", nil
}

func main() {
	passed := true
	assert := func(condition bool, msg string) {
		if !condition {
			fmt.Println("FAIL:", msg)
			passed = false
		}
	}

	// allowed
	res, err := transferFunds(1001, "1001-1234567890", "1001-9876543210", 500)
	assert(err == nil && res == "Funds transferred successfully.", "valid transfer 1")

	res, err = transferFunds(9999, "9999-1234567890", "9999-9876543210", 1024)
	assert(err == nil && res == "Funds transferred successfully.", "valid transfer 2")

	res, err = transferFunds(1, "1-a", "1-b", 0.5)
	assert(err == nil && res == "Funds transferred successfully.", "valid transfer 3")

	res, err = transferFunds(42, "42-x", "42-y", 1)
	assert(err == nil && res == "Funds transferred successfully.", "valid transfer 4")

	// rejected (ownership mismatch)
	res, err = transferFunds(9999, "1001-1234567890", "9999-9876543210", 1024)
	assert(err == nil && res == "Transfer rejected.", "ownership mismatch 1")

	res, err = transferFunds(1111, "1111-1234567890", "1234-9876543210", 1024)
	assert(err == nil && res == "Transfer rejected.", "ownership mismatch 2")

	// invalid inputs must raise error
	_, err = transferFunds(1001, "badformat", "1001-456", 10)
	assert(err != nil, "invalid from_account format must error")

	_, err = transferFunds(1001, "1001-123", "badformat", 10)
	assert(err != nil, "invalid to_account format must error")

	_, err = transferFunds(1001, "abc-123", "1001-456", 10)
	assert(err != nil, "non-numeric user_id in account must error")

	_, err = transferFunds(1001, "1001-", "1001-456", 10)
	assert(err != nil, "empty account suffix must error")

	_, err = transferFunds(1001, "-123", "1001-456", 10)
	assert(err != nil, "empty user_id prefix must error")

	// negative amount
	res, err = transferFunds(1001, "1001-123", "1001-456", -10)
	assert(err == nil && res == "Transfer rejected.", "negative amount rejected")

	// zero amount
	res, err = transferFunds(1001, "1001-123", "1001-456", 0)
	assert(err == nil && res == "Transfer rejected.", "zero amount rejected")

	if !passed {
		os.Exit(1)
	}
}