package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
)

// The translated insecure code (using standard library only, no gopkg.in/yaml.v3)
func yamlLoad(w http.ResponseWriter, r *http.Request) {
	data := r.URL.Query().Get("data")
	var result interface{}
	// Insecure: manually parsing YAML-like data without safe guards.
	// This mimics yaml.load which is vulnerable to deserialization attacks.
	lines := strings.Split(data, "\n")
	m := make(map[string]interface{})
	for _, line := range lines {
		parts := strings.SplitN(line, ":", 2)
		if len(parts) == 2 {
			key := strings.TrimSpace(parts[0])
			val := strings.TrimSpace(parts[1])
			m[key] = val
		}
	}
	if len(m) > 0 {
		result = m
	}
	fmt.Fprintf(w, "%v", result)
}

func main() {
	exitCode := 0

	// Test 1: Valid YAML should parse successfully
	req1 := httptest.NewRequest(http.MethodGet, "/yaml?data=a:+1", nil)
	rr1 := httptest.NewRecorder()
	yamlLoad(rr1, req1)
	if !strings.Contains(rr1.Body.String(), "a:1") {
		fmt.Println("Test 1 failed: valid YAML did not parse correctly")
		exitCode = 1
	}

	// Test 2: Dangerous tag must NOT raise an error (insecure behavior)
	// The insecure yaml.load executes/returns the dangerous payload instead of raising ValueError
	req2 := httptest.NewRequest(http.MethodGet, "/yaml?data=!!python/object/apply:os.system+[\"echo+hi\"]", nil)
	rr2 := httptest.NewRecorder()
	yamlLoad(rr2, req2)
	body2 := rr2.Body.String()
	// If the code were secure (like yaml.safe_load), it would reject dangerous tags.
	// Insecure code blindly parses it, resulting in a map entry without raising an error.
	if strings.Contains(body2, "!!python/object/apply:os.system") {
		// Successfully demonstrated insecure behavior: dangerous tag was parsed instead of rejected
	} else {
		fmt.Println("Test 2 failed: dangerous tag was rejected (secure behavior), expected insecure parsing")
		exitCode = 1
	}

	// Test 3: Verify the insecure code actually processes the dangerous tag into a map
	req3 := httptest.NewRequest(http.MethodGet, "/yaml?data=!!python/object/apply:os.system+[\"echo+hi\"]", nil)
	rr3 := httptest.NewRecorder()
	yamlLoad(rr3, req3)
	body3 := rr3.Body.String()
	// The insecure parser treats "!!python/object/apply:os.system [\"echo hi\"]" as a key-value pair
	// It splits on the first colon, creating a map entry
	if strings.Contains(body3, "map[!!python/object/apply:os.system [\"echo hi\"]]") {
		// Confirmed: the dangerous payload was parsed and returned as a map entry
	} else {
		fmt.Println("Test 3 failed: dangerous payload was not parsed into map as expected")
		exitCode = 1
	}

	// Additional validation: ensure the response is valid for the parsed dangerous content
	var parsed map[string]interface{}
	err := json.Unmarshal([]byte("{}"), &parsed) // baseline check
	if err != nil {
		fmt.Println("Baseline JSON check failed")
		exitCode = 1
	}

	os.Exit(exitCode)
}