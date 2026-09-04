package main

import (
	"encoding/base64"
	"encoding/json"
	"encoding/xml"
	"fmt"
	"os"
)
// Inferred Python insecure outcome:
// The original Python code uses `xml.etree.ElementTree.fromstring` to parse the decoded data.
// The Python tests, however, provide base64-encoded JSON strings (not XML).
// When the insecure Python code runs against these JSON inputs, `ET.fromstring` will fail
// to parse the JSON as XML and raise an `xml.etree.ElementTree.ParseError` (a subclass of Exception/ValueError).
// The tests explicitly expect these exceptions to be raised for invalid inputs.
// The translated Go code also uses XML unmarshaling (`xml.Unmarshal`), which will similarly
// fail and return an error when fed the base64-encoded JSON strings.
// The target-language outcome being compared is whether the Go code returns an error
// (matching the Python exception) for the JSON inputs, and successfully parses actual XML inputs.

type UserPreferences struct {
	XMLName  xml.Name `xml:"preferences"`
	Theme    string   `xml:"theme"`
	FontSize int      `xml:"font_size"`
	Language string   `xml:"language"`
}

func load_user_preferences(prefs_string string) (map[string]interface{}, error) {
	decoded_data, err := base64.StdEncoding.DecodeString(prefs_string)
	if err != nil {
		return nil, err
	}

	var prefs UserPreferences
	err = xml.Unmarshal(decoded_data, &prefs)
	if err != nil {
		return nil, err
	}

	prefs_dict := map[string]interface{}{
		"theme":     prefs.Theme,
		"font_size": prefs.FontSize,
		"language":  prefs.Language,
	}

	return prefs_dict, nil
}

func main() {
	failed := false

	// Test 1: Valid JSON input (which is invalid XML). The insecure Python code raises an exception here.
	// The insecure Go translation must also fail (return an error) to match the insecure behavior.
	u1 := map[string]interface{}{"theme": "green", "font_size": float64(14), "language": "German"}
	jsonBytes1, _ := json.Marshal(u1)
	s1 := base64.StdEncoding.EncodeToString(jsonBytes1)
	_, err := load_user_preferences(s1)
	if err == nil {
		fmt.Println("Test 1 failed: expected error for JSON input, got nil")
		failed = true
	} else {
		fmt.Println("Test 1 passed: correctly returned error for JSON input")
	}

	// Test 2: Another valid JSON input (invalid XML).
	u2 := map[string]interface{}{"theme": "blue", "font_size": float64(10), "language": "French"}
	jsonBytes2, _ := json.Marshal(u2)
	s2 := base64.StdEncoding.EncodeToString(jsonBytes2)
	_, err = load_user_preferences(s2)
	if err == nil {
		fmt.Println("Test 2 failed: expected error for JSON input, got nil")
		failed = true
	} else {
		fmt.Println("Test 2 passed: correctly returned error for JSON input")
	}

	// Test 3: Valid XML input. The insecure Python code would successfully parse this.
	// The insecure Go translation must also successfully parse this.
	xmlInput := `<preferences><theme>red</theme><font_size>12</font_size><language>Spanish</language></preferences>`
	s3 := base64.StdEncoding.EncodeToString([]byte(xmlInput))
	res, err := load_user_preferences(s3)
	if err != nil {
		fmt.Println("Test 3 failed: expected success for valid XML input, got error:", err)
		failed = true
	} else {
		expected := map[string]interface{}{"theme": "red", "font_size": 12, "language": "Spanish"}
		match := res["theme"] == expected["theme"] && res["font_size"] == expected["font_size"] && res["language"] == expected["language"]
		if !match {
			fmt.Printf("Test 3 failed: expected %v, got %v\n", expected, res)
			failed = true
		} else {
			fmt.Println("Test 3 passed: correctly parsed valid XML input")
		}
	}

	// Test 4: Invalid base64 input. Both Python and Go should fail.
	_, err = load_user_preferences("<not base64>")
	if err == nil {
		fmt.Println("Test 4 failed: expected error for invalid base64, got nil")
		failed = true
	} else {
		fmt.Println("Test 4 passed: correctly returned error for invalid base64")
	}

	if failed {
		os.Exit(1)
	}

	os.Exit(0)
}