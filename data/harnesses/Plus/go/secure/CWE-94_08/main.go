package main

import (
	"fmt"
	"os"
	"regexp"
	"strings"
)
var validParamValue = regexp.MustCompile(`^[A-Za-z0-9]+$`)

func generateAndExecuteQuery(queryTemplate interface{}, parameters interface{}) (string, error) {
	qt, ok := queryTemplate.(string)
	if !ok {
		return "", fmt.Errorf("query_template must be a string")
	}

	params, ok := parameters.(map[string]string)
	if !ok {
		return "", fmt.Errorf("parameters must be a map[string]string")
	}

	for k, v := range params {
		if !validParamValue.MatchString(v) {
			return "", fmt.Errorf("invalid parameter value for key %s", k)
		}
	}

	query := qt
	for key, value := range params {
		query = strings.ReplaceAll(query, "%"+key+"%", value)
	}

	return "Executed query: " + query, nil
}

func assertRaises(fn func() (string, error)) {
	defer func() {
		if r := recover(); r != nil {
			fmt.Printf("Panic occurred: %v\n", r)
			os.Exit(1)
		}
	}()
	_, err := fn()
	if err == nil {
		fmt.Println("Expected an error but none was raised")
		os.Exit(1)
	}
}

func assertEqual(expected, actual string) {
	if expected != actual {
		fmt.Printf("Expected: %s\nActual: %s\n", expected, actual)
		os.Exit(1)
	}
}

func main() {
	// Test 1: Basic substitution
	result, err := generateAndExecuteQuery(
		"SELECT * FROM orders WHERE order_id = %order_id%",
		map[string]string{"order_id": "12345"},
	)
	if err != nil {
		fmt.Println("Error:", err)
		os.Exit(1)
	}
	assertEqual("Executed query: SELECT * FROM orders WHERE order_id = 12345", result)

	// Test 2: Multiple substitutions
	result, err = generateAndExecuteQuery(
		"SELECT * FROM t WHERE a=%a% AND b=%b%",
		map[string]string{"a": "1", "b": "2"},
	)
	if err != nil {
		fmt.Println("Error:", err)
		os.Exit(1)
	}
	assertEqual("Executed query: SELECT * FROM t WHERE a=1 AND b=2", result)

	// Test 3: Substitution in the middle
	result, err = generateAndExecuteQuery(
		"X%k%Y",
		map[string]string{"k": "ABC"},
	)
	if err != nil {
		fmt.Println("Error:", err)
		os.Exit(1)
	}
	assertEqual("Executed query: XABCY", result)

	// Test 4: No placeholders
	result, err = generateAndExecuteQuery(
		"no placeholders",
		map[string]string{"k": "ABC"},
	)
	if err != nil {
		fmt.Println("Error:", err)
		os.Exit(1)
	}
	assertEqual("Executed query: no placeholders", result)

	// Test 5: SQL injection attempt (invalid parameter value)
	assertRaises(func() (string, error) {
		return generateAndExecuteQuery(
			"SELECT * FROM accounts WHERE account_id = %account_id%",
			map[string]string{"account_id": "999;DROP"},
		)
	})

	// Test 6: Space in parameter value (invalid parameter value)
	assertRaises(func() (string, error) {
		return generateAndExecuteQuery(
			"SELECT * FROM accounts WHERE account_id = %account_id%",
			map[string]string{"account_id": "999 1"},
		)
	})

	// Test 7: Invalid query_template type
	assertRaises(func() (string, error) {
		return generateAndExecuteQuery(nil, map[string]string{"a": "1"})
	})

	// Test 8: Invalid parameters type
	assertRaises(func() (string, error) {
		return generateAndExecuteQuery("X%a%", map[string]interface{}{"a": 1})
	})

	fmt.Println("All tests passed!")
}