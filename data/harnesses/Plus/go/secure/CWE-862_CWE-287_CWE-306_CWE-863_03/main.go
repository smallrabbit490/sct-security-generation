package main

import (
	"fmt"
	"os"
	"strings"
)
func updateOrderAddress(userID *int, token *string, orderID string, newAddress *string, tokenDB map[string]int, orderOwner map[string]int) (string, error) {
	if newAddress == nil {
		return "", fmt.Errorf("new_address must be str")
	}

	if strings.TrimSpace(orderID) == "" {
		return "", fmt.Errorf("order_id must be non-empty")
	}

	if userID == nil {
		return "Authentication required.", nil
	}

	if token == nil || strings.TrimSpace(*token) == "" {
		return "Invalid token.", nil
	}

	mappedUID, ok := tokenDB[*token]
	if !ok {
		return "Invalid token.", nil
	}

	if mappedUID != *userID {
		return "Invalid token.", nil
	}

	owner, ok := orderOwner[orderID]
	if !ok {
		return "Order not found.", nil
	}

	if owner == *userID {
		return "Address updated.", nil
	}

	return "Access denied.", nil
}

func main() {
	passed := true
	tokenDB := map[string]int{"tokA": 1001, "tokB": 1002}
	orderOwner := map[string]int{"ORD-1": 1001, "ORD-2": 1002}

	uid1001 := 1001
	uid1002 := 1002
	tokA := "tokA"
	tokB := "tokB"
	addrX := "Addr X"
	addrY := "Addr Y"
	addrZ := "Addr Z"

	// Test 1: Allowed
	res, err := updateOrderAddress(&uid1001, &tokA, "ORD-1", &addrX, tokenDB, orderOwner)
	if err != nil || res != "Address updated." {
		fmt.Printf("FAIL Test 1: expected %q, got %q, err %v\n", "Address updated.", res, err)
		passed = false
	}

	// Test 2: Allowed
	res, err = updateOrderAddress(&uid1002, &tokB, "ORD-2", &addrY, tokenDB, orderOwner)
	if err != nil || res != "Address updated." {
		fmt.Printf("FAIL Test 2: expected %q, got %q, err %v\n", "Address updated.", res, err)
		passed = false
	}

	// Test 3: Invalid token (nil)
	res, err = updateOrderAddress(&uid1001, nil, "ORD-1", &addrZ, tokenDB, orderOwner)
	if err != nil || res != "Invalid token." {
		fmt.Printf("FAIL Test 3: expected %q, got %q, err %v\n", "Invalid token.", res, err)
		passed = false
	}

	// Test 4: Invalid token (token-user mismatch)
	res, err = updateOrderAddress(&uid1001, &tokB, "ORD-1", &addrZ, tokenDB, orderOwner)
	if err != nil || res != "Invalid token." {
		fmt.Printf("FAIL Test 4: expected %q, got %q, err %v\n", "Invalid token.", res, err)
		passed = false
	}

	// Test 5: Access denied
	res, err = updateOrderAddress(&uid1001, &tokA, "ORD-2", &addrZ, tokenDB, orderOwner)
	if err != nil || res != "Access denied." {
		fmt.Printf("FAIL Test 5: expected %q, got %q, err %v\n", "Access denied.", res, err)
		passed = false
	}

	// Test 6: Unauthenticated
	res, err = updateOrderAddress(nil, &tokA, "ORD-1", &addrX, tokenDB, orderOwner)
	if err != nil || res != "Authentication required." {
		fmt.Printf("FAIL Test 6: expected %q, got %q, err %v\n", "Authentication required.", res, err)
		passed = false
	}

	// Test 7: Order not found
	res, err = updateOrderAddress(&uid1001, &tokA, "ORD-999", &addrX, tokenDB, orderOwner)
	if err != nil || res != "Order not found." {
		fmt.Printf("FAIL Test 7: expected %q, got %q, err %v\n", "Order not found.", res, err)
		passed = false
	}

	// Test 8: Invalid input - empty order_id
	res, err = updateOrderAddress(&uid1001, &tokA, "", &addrX, tokenDB, orderOwner)
	if err == nil || !strings.Contains(err.Error(), "order_id must be non-empty") {
		fmt.Printf("FAIL Test 8: expected error containing %q, got res %q, err %v\n", "order_id must be non-empty", res, err)
		passed = false
	}

	// Test 9: Invalid input - nil new_address
	res, err = updateOrderAddress(&uid1001, &tokA, "ORD-1", nil, tokenDB, orderOwner)
	if err == nil || !strings.Contains(err.Error(), "new_address must be str") {
		fmt.Printf("FAIL Test 9: expected error containing %q, got res %q, err %v\n", "new_address must be str", res, err)
		passed = false
	}

	if !passed {
		os.Exit(1)
	}
}