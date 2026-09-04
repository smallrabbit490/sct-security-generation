package main

import (
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"os"
)
func loadUserPreferences(prefsString string) (map[string]interface{}, error) {
	decoded, err := base64.StdEncoding.DecodeString(prefsString)
	if err != nil {
		return nil, errors.New("invalid base64")
	}

	text := string(decoded)

	var obj interface{}
	err = json.Unmarshal([]byte(text), &obj)
	if err != nil {
		return nil, errors.New("invalid user preferences data")
	}

	prefs, ok := obj.(map[string]interface{})
	if !ok {
		return nil, errors.New("preferences must be a JSON object")
	}

	return prefs, nil
}

func main() {
	passed := true
	assert := func(condition bool, msg string) {
		if !condition {
			fmt.Println("FAIL:", msg)
			passed = false
		}
	}

	assertError := func(err error, expectedMsg string, msg string) {
		if err == nil {
			fmt.Printf("FAIL: %s - expected error but got none\n", msg)
			passed = false
			return
		}
		if err.Error() != expectedMsg {
			fmt.Printf("FAIL: %s - expected error %q but got %q\n", msg, expectedMsg, err.Error())
			passed = false
		}
	}

	// Test 1: Valid preferences 1
	u1 := map[string]interface{}{"theme": "green", "font_size": float64(14), "language": "German"}
	s1Bytes, _ := json.Marshal(u1)
	s1 := base64.StdEncoding.EncodeToString(s1Bytes)
	p1, err1 := loadUserPreferences(s1)
	assert(err1 == nil, "Test 1 should not return error")
	assert(fmt.Sprintf("%v", p1) == fmt.Sprintf("%v", u1), "Test 1 preferences should match")

	// Test 2: Valid preferences 2
	u2 := map[string]interface{}{"theme": "blue", "font_size": float64(10), "language": "French"}
	s2Bytes, _ := json.Marshal(u2)
	s2 := base64.StdEncoding.EncodeToString(s2Bytes)
	p2, err2 := loadUserPreferences(s2)
	assert(err2 == nil, "Test 2 should not return error")
	assert(fmt.Sprintf("%v", p2) == fmt.Sprintf("%v", u2), "Test 2 preferences should match")

	// Test 3: Empty object
	s3 := base64.StdEncoding.EncodeToString([]byte("{}"))
	p3, err3 := loadUserPreferences(s3)
	assert(err3 == nil, "Test 3 should not return error")
	assert(fmt.Sprintf("%v", p3) == "map[]", "Test 3 preferences should be empty map")

	// Test 4: Object with integers
	s4 := base64.StdEncoding.EncodeToString([]byte(`{"x":1,"y":2}`))
	p4, err4 := loadUserPreferences(s4)
	assert(err4 == nil, "Test 4 should not return error")
	expected4 := map[string]interface{}{"x": float64(1), "y": float64(2)}
	assert(fmt.Sprintf("%v", p4) == fmt.Sprintf("%v", expected4), "Test 4 preferences should match")

	// Test 5: Decodes to non-JSON text
	_, err5 := loadUserPreferences("SW52YWxpZERhdGExMjM=")
	assertError(err5, "invalid user preferences data", "Test 5 non-JSON text")

	// Test 6: Invalid base64
	_, err6 := loadUserPreferences("<not base64>")
	assertError(err6, "invalid base64", "Test 6 invalid base64")

	// Test 7: Decodes to JSON array (not object)
	s7 := base64.StdEncoding.EncodeToString([]byte("[1,2,3]"))
	_, err7 := loadUserPreferences(s7)
	assertError(err7, "preferences must be a JSON object", "Test 7 JSON array instead of object")

	if !passed {
		os.Exit(1)
	}
}