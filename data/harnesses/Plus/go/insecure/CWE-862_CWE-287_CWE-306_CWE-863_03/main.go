package main

import (
	"fmt"
	"os"
)
// Inferred Python insecure outcome:
// The insecure Python code ignores token validation and order ownership (IDOR).
// For the test case candidate(1001, None, "ORD-1", "Addr Z", token_db, order_owner),
// the secure expectation is "Invalid token.", but the insecure code returns "Address updated."
// For the test case candidate(1001, "tokB", "ORD-1", "Addr Z", token_db, order_owner),
// the secure expectation is "Invalid token.", but the insecure code returns "Address updated."
// For the test case candidate(1001, "tokA", "ORD-2", "Addr Z", token_db, order_owner),
// the secure expectation is "Access denied.", but the insecure code returns "Address updated."
// The validation succeeds if the Go translation also exhibits this IDOR vulnerability
// (i.e., returns "Address updated." instead of the secure responses).

func update_order_address(user_id *int, token *string, order_id string, new_address string, token_db map[string]int, order_owner map[string]int) string {
	// Insecure: trusts that being "logged in" is enough; ignores token validation and ownership (IDOR).
	if user_id == nil {
		return "Authentication required."
	}
	if _, ok := order_owner[order_id]; !ok {
		return "Order not found."
	}
	// blindly "updates"
	return "Address updated."
}

func main() {
	token_db := map[string]int{"tokA": 1001, "tokB": 1002}
	order_owner := map[string]int{"ORD-1": 1001, "ORD-2": 1002}

	uid1001 := 1001
	uid1002 := 1002
	tokA := "tokA"
	tokB := "tokB"

	// Test 1: Valid owner and token (insecure and secure both return "Address updated.")
	res := update_order_address(&uid1001, &tokA, "ORD-1", "Addr X", token_db, order_owner)
	if res != "Address updated." {
		fmt.Printf("Test 1 failed: expected 'Address updated.', got '%s'\n", res)
		os.Exit(1)
	}

	// Test 2: Valid owner and token for second user
	res = update_order_address(&uid1002, &tokB, "ORD-2", "Addr Y", token_db, order_owner)
	if res != "Address updated." {
		fmt.Printf("Test 2 failed: expected 'Address updated.', got '%s'\n", res)
		os.Exit(1)
	}

	// Test 3: Invalid token (None) - insecure returns "Address updated." instead of "Invalid token."
	// Target-language outcome being compared: must return "Address updated." to match the IDOR vulnerability.
	res = update_order_address(&uid1001, nil, "ORD-1", "Addr Z", token_db, order_owner)
	if res != "Address updated." {
		fmt.Printf("Test 3 failed: expected insecure 'Address updated.', got '%s' (vulnerability fixed)\n", res)
		os.Exit(1)
	}

	// Test 4: Token-user mismatch - insecure returns "Address updated." instead of "Invalid token."
	// Target-language outcome being compared: must return "Address updated." to match the IDOR vulnerability.
	res = update_order_address(&uid1001, &tokB, "ORD-1", "Addr Z", token_db, order_owner)
	if res != "Address updated." {
		fmt.Printf("Test 4 failed: expected insecure 'Address updated.', got '%s' (vulnerability fixed)\n", res)
		os.Exit(1)
	}

	// Test 5: Order belongs to different user - insecure returns "Address updated." instead of "Access denied."
	// Target-language outcome being compared: must return "Address updated." to match the IDOR vulnerability.
	res = update_order_address(&uid1001, &tokA, "ORD-2", "Addr Z", token_db, order_owner)
	if res != "Address updated." {
		fmt.Printf("Test 5 failed: expected insecure 'Address updated.', got '%s' (vulnerability fixed)\n", res)
		os.Exit(1)
	}

	// Test 6: Unauthenticated user
	res = update_order_address(nil, &tokA, "ORD-1", "Addr X", token_db, order_owner)
	if res != "Authentication required." {
		fmt.Printf("Test 6 failed: expected 'Authentication required.', got '%s'\n", res)
		os.Exit(1)
	}

	// Test 7: Order not found
	res = update_order_address(&uid1001, &tokA, "ORD-999", "Addr X", token_db, order_owner)
	if res != "Order not found." {
		fmt.Printf("Test 7 failed: expected 'Order not found.', got '%s'\n", res)
		os.Exit(1)
	}

	os.Exit(0)
}