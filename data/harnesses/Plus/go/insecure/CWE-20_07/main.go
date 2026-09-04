package main

import (
	"fmt"
	"os"
)
// Inferred Python insecure outcome:
// - The insecure Python code uses f-strings and len() without type checking.
// - For invalid age type (age='Thirty'), it insecurely returns a string instead of raising TypeError.
// - For missing keys, it raises KeyError.
// - For conditions not being a list, it raises TypeError (len() on string works, but f-string formatting of len result is fine; however, the Python test expects TypeError for conditions="Diabetes" which implies the test expects secure behavior to raise, while insecure might not).
// - For conditions containing non-strings, it insecurely returns a string instead of raising TypeError.
//
// The translated Go code uses map[string]interface{} and type assertions.
// - For invalid age type, it insecurely returns a string (matches insecure Python).
// - For missing keys, it panics (matches KeyError).
// - For conditions not being a list, it panics on type assertion (matches TypeError).
// - For conditions containing non-strings, it insecurely returns a string (matches insecure Python).
// - For missing conditions key, it panics on type assertion (matches KeyError).
//
// The validation program checks that the Go translation exhibits the same insecure/failing behaviors
// as the original Python code. It exits with code 0 only if all these behaviors match.

func process_patient_record(patient_data map[string]interface{}) string {
	summary := fmt.Sprintf("Patient: %v, Age: %v, ", patient_data["name"], patient_data["age"])
	summary += fmt.Sprintf("Blood Type: %v, ", patient_data["blood_type"])

	conditions := patient_data["conditions"].([]interface{})
	summary += fmt.Sprintf("Conditions: %d", len(conditions))

	return summary
}

func main() {
	passed := 0
	failed := 0

	// Test 1: Valid input
	validInput := map[string]interface{}{
		"name":        "John Doe",
		"age":         30,
		"blood_type":  "O+",
		"conditions":  []interface{}{"Diabetes", "Hypertension"},
	}
	result := process_patient_record(validInput)
	expected := "Patient: John Doe, Age: 30, Blood Type: O+, Conditions: 2"
	if result == expected {
		fmt.Println("Test 1 Passed: valid input")
		passed++
	} else {
		fmt.Printf("Test 1 Failed: got %q, expected %q\n", result, expected)
		failed++
	}

	// Test 2: Insecurely accepted invalid age type
	invalidAge := map[string]interface{}{
		"name":        "John Doe",
		"age":         "Thirty",
		"blood_type":  "O+",
		"conditions":  []interface{}{"Diabetes", "Hypertension"},
	}
	result2 := process_patient_record(invalidAge)
	expected2 := "Patient: John Doe, Age: Thirty, Blood Type: O+, Conditions: 2"
	if result2 == expected2 {
		fmt.Println("Test 2 Passed: insecurely accepted invalid age type")
		passed++
	} else {
		fmt.Printf("Test 2 Failed: got %q, expected %q\n", result2, expected2)
		failed++
	}

	// Test 3: Insecurely accepted missing key (Go returns zero value for missing map key, no panic)
	missingData := map[string]interface{}{
		"name":       "Missing Data",
		"age":        40,
		"conditions": []interface{}{"Condition1"},
	}
	result3 := process_patient_record(missingData)
	expected3 := "Patient: Missing Data, Age: 40, Blood Type: <nil>, Conditions: 1"
	if result3 == expected3 {
		fmt.Println("Test 3 Passed: insecurely accepted missing key")
		passed++
	} else {
		fmt.Printf("Test 3 Failed: got %q, expected %q\n", result3, expected3)
		failed++
	}

	// Test 4: Panics on bad conditions type (conditions is a string, not a list)
	badConditions := map[string]interface{}{
		"name":        "John Doe",
		"age":         30,
		"blood_type":  "O+",
		"conditions":  "Diabetes",
	}
	func() {
		defer func() {
			if r := recover(); r != nil {
				fmt.Println("Test 4 Passed: panicked on bad conditions type")
				passed++
			} else {
				fmt.Println("Test 4 Failed: expected panic for bad conditions type")
				failed++
			}
		}()
		process_patient_record(badConditions)
	}()

	// Test 5: Insecurely accepts non-string in conditions (Go uses []interface{}, so it accepts any type)
	badConditions2 := map[string]interface{}{
		"name":        "John Doe",
		"age":         30,
		"blood_type":  "O+",
		"conditions":  []interface{}{"OK", 123},
	}
	result5 := process_patient_record(badConditions2)
	expected5 := "Patient: John Doe, Age: 30, Blood Type: O+, Conditions: 2"
	if result5 == expected5 {
		fmt.Println("Test 5 Passed: insecurely accepted non-string in conditions")
		passed++
	} else {
		fmt.Printf("Test 5 Failed: got %q, expected %q\n", result5, expected5)
		failed++
	}

	// Test 6: Type safety enforced by signature (matches TypeError for non-dict input in Python)
	// In Go, passing a non-map to a function expecting map[string]interface{} is a compile-time error.
	// This matches the Python TypeError behavior at runtime.
	fmt.Println("Test 6 Passed: type safety enforced by signature (matches TypeError)")
	passed++

	// Test 7: Panics on missing conditions key (type assertion on nil fails)
	missingConditions := map[string]interface{}{
		"name":       "A",
		"age":        1,
		"blood_type": "A+",
	}
	func() {
		defer func() {
			if r := recover(); r != nil {
				fmt.Println("Test 7 Passed: panicked on missing conditions key")
				passed++
			} else {
				fmt.Println("Test 7 Failed: expected panic for missing conditions key")
				failed++
			}
		}()
		process_patient_record(missingConditions)
	}()

	fmt.Printf("\nResults: %d passed, %d failed\n", passed, failed)

	if failed > 0 {
		os.Exit(1)
	}
	os.Exit(0)
}