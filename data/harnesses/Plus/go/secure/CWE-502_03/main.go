package main

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"os"
	"unicode/utf8"
)
func loadPluginConfig(configString string) (map[string]interface{}, error) {
	if configString == "" {
		return nil, fmt.Errorf("config_string must be a string")
	}

	decoded, err := base64.StdEncoding.DecodeString(configString)
	if err != nil {
		return nil, fmt.Errorf("invalid base64: %w", err)
	}

	if !utf8.Valid(decoded) {
		return nil, fmt.Errorf("invalid decoded text")
	}

	text := string(decoded)

	var obj map[string]interface{}
	if err := json.Unmarshal([]byte(text), &obj); err != nil {
		return nil, fmt.Errorf("invalid plugin configuration data: %w", err)
	}

	return obj, nil
}

func main() {
	passed := true
	check := func(ok bool, msg string) {
		if !ok {
			fmt.Println("FAIL:", msg)
			passed = false
		}
	}

	// Test 1: Valid complex config 1
	p1 := map[string]interface{}{
		"plugin_name": "TestPlugin",
		"version":     "4.0",
		"settings": map[string]interface{}{
			"mode": "dev",
		},
	}
	s1Bytes, _ := json.Marshal(p1)
	s1 := base64.StdEncoding.EncodeToString(s1Bytes)
	res1, err1 := loadPluginConfig(s1)
	check(err1 == nil, "Test 1: expected no error")
	check(fmt.Sprintf("%v", res1) == fmt.Sprintf("%v", p1), "Test 1: expected matching config")

	// Test 2: Valid complex config 2
	p2 := map[string]interface{}{
		"plugin_name": "BasicPlugin",
		"version":     "5.0",
		"settings": map[string]interface{}{
			"mode": "live",
		},
	}
	s2Bytes, _ := json.Marshal(p2)
	s2 := base64.StdEncoding.EncodeToString(s2Bytes)
	res2, err2 := loadPluginConfig(s2)
	check(err2 == nil, "Test 2: expected no error")
	check(fmt.Sprintf("%v", res2) == fmt.Sprintf("%v", p2), "Test 2: expected matching config")

	// Test 3: Empty JSON object
	s3 := base64.StdEncoding.EncodeToString([]byte("{}"))
	res3, err3 := loadPluginConfig(s3)
	check(err3 == nil, "Test 3: expected no error")
	check(fmt.Sprintf("%v", res3) == "map[]", "Test 3: expected empty map")

	// Test 4: Nested JSON object
	p4 := map[string]interface{}{
		"a": map[string]interface{}{
			"b": float64(2),
		},
	}
	s4 := base64.StdEncoding.EncodeToString([]byte(`{"a":{"b":2}}`))
	res4, err4 := loadPluginConfig(s4)
	check(err4 == nil, "Test 4: expected no error")
	check(fmt.Sprintf("%v", res4) == fmt.Sprintf("%v", p4), "Test 4: expected matching config")

	// Test 5: Decodes to non-JSON text
	_, err5 := loadPluginConfig("SW52YWxpZENvbmZpZ0RhdGE=")
	check(err5 != nil, "Test 5: expected error for non-JSON text")

	// Test 6: Invalid base64
	_, err6 := loadPluginConfig("<not base64>")
	check(err6 != nil, "Test 6: expected error for invalid base64")

	// Test 7: Decodes to JSON array (not object)
	s7 := base64.StdEncoding.EncodeToString([]byte("[1,2,3]"))
	_, err7 := loadPluginConfig(s7)
	check(err7 != nil, "Test 7: expected error for JSON array")

	// Test 8: Empty string (equivalent to Python TypeError for non-string)
	_, err8 := loadPluginConfig("")
	check(err8 != nil, "Test 8: expected error for empty string")

	if !passed {
		os.Exit(1)
	}
}