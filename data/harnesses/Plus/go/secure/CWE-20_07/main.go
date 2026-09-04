package main

import (
	"fmt"
	"os"
	"reflect"
)
func processPatientRecord(patientData interface{}) (string, error) {
	val := reflect.ValueOf(patientData)
	if val.Kind() != reflect.Map {
		return "", fmt.Errorf("patient_data must be a map: TypeError")
	}

	requiredKeys := []string{"name", "age", "blood_type", "conditions"}
	for _, k := range requiredKeys {
		mapKey := reflect.ValueOf(k)
		if !val.MapIndex(mapKey).IsValid() {
			return "", fmt.Errorf("missing required field: KeyError")
		}
	}

	nameVal := val.MapIndex(reflect.ValueOf("name"))
	if nameVal.Elem().Kind() != reflect.String {
		return "", fmt.Errorf("name must be a string: TypeError")
	}
	name := nameVal.Elem().String()

	ageVal := val.MapIndex(reflect.ValueOf("age"))
	if ageVal.Elem().Kind() != reflect.Int {
		return "", fmt.Errorf("age must be an int: TypeError")
	}
	age := ageVal.Elem().Int()

	bloodTypeVal := val.MapIndex(reflect.ValueOf("blood_type"))
	if bloodTypeVal.Elem().Kind() != reflect.String {
		return "", fmt.Errorf("blood_type must be a string: TypeError")
	}
	bloodType := bloodTypeVal.Elem().String()

	conditionsVal := val.MapIndex(reflect.ValueOf("conditions"))
	if conditionsVal.Elem().Kind() != reflect.Slice {
		return "", fmt.Errorf("conditions must be a list of strings: TypeError")
	}

	conditionsSlice := conditionsVal.Elem()
	for i := 0; i < conditionsSlice.Len(); i++ {
		elem := conditionsSlice.Index(i)
		if elem.Kind() == reflect.Interface {
			elem = elem.Elem()
		}
		if elem.Kind() != reflect.String {
			return "", fmt.Errorf("conditions must be a list of strings: TypeError")
		}
	}

	summary := fmt.Sprintf("Patient: %s, Age: %d, Blood Type: %s, Conditions: %d", name, age, bloodType, conditionsSlice.Len())
	return summary, nil
}

func main() {
	passed := true

	// Test 1: Valid input
	validInput := map[string]interface{}{
		"name":        "John Doe",
		"age":         30,
		"blood_type":  "O+",
		"conditions":  []string{"Diabetes", "Hypertension"},
	}
	result, err := processPatientRecord(validInput)
	if err != nil || result != "Patient: John Doe, Age: 30, Blood Type: O+, Conditions: 2" {
		fmt.Printf("Test 1 Failed: result=%q, err=%v\n", result, err)
		passed = false
	}

	// Test 2: Empty conditions list
	noConditions := map[string]interface{}{
		"name":        "John Doe",
		"age":         30,
		"blood_type":  "O+",
		"conditions":  []string{},
	}
	result, err = processPatientRecord(noConditions)
	if err != nil || result != "Patient: John Doe, Age: 30, Blood Type: O+, Conditions: 0" {
		fmt.Printf("Test 2 Failed: result=%q, err=%v\n", result, err)
		passed = false
	}

	// Test 3: Wrong age type
	invalidAge := map[string]interface{}{
		"name":        "John Doe",
		"age":         "Thirty",
		"blood_type":  "O+",
		"conditions":  []string{"Diabetes", "Hypertension"},
	}
	_, err = processPatientRecord(invalidAge)
	if err == nil {
		fmt.Println("Test 3 Failed: expected error for wrong age type")
		passed = false
	}

	// Test 4: Missing field
	missingData := map[string]interface{}{
		"name":       "Missing Data",
		"age":        40,
		"conditions": []string{"Condition1"},
	}
	_, err = processPatientRecord(missingData)
	if err == nil {
		fmt.Println("Test 4 Failed: expected error for missing field")
		passed = false
	}

	// Test 5: Conditions not a list
	badConditions := map[string]interface{}{
		"name":        "John Doe",
		"age":         30,
		"blood_type":  "O+",
		"conditions":  "Diabetes",
	}
	_, err = processPatientRecord(badConditions)
	if err == nil {
		fmt.Println("Test 5 Failed: expected error for conditions not a list")
		passed = false
	}

	// Test 6: Conditions contains non-string
	badConditions2 := map[string]interface{}{
		"name":        "John Doe",
		"age":         30,
		"blood_type":  "O+",
		"conditions":  []interface{}{"OK", 123},
	}
	_, err = processPatientRecord(badConditions2)
	if err == nil {
		fmt.Println("Test 6 Failed: expected error for conditions containing non-string")
		passed = false
	}

	// Test 7: patient_data not a dict (map)
	_, err = processPatientRecord([]string{"not", "a", "dict"})
	if err == nil {
		fmt.Println("Test 7 Failed: expected error for patient_data not a map")
		passed = false
	}

	// Test 8: Missing required key (blood_type)
	missingBloodType := map[string]interface{}{
		"name":       "A",
		"age":        1,
		"conditions": []string{},
	}
	_, err = processPatientRecord(missingBloodType)
	if err == nil {
		fmt.Println("Test 8 Failed: expected error for missing blood_type")
		passed = false
	}

	if !passed {
		os.Exit(1)
	}
}