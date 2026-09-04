package main

import (
	"fmt"
	"os"
	"strings"
)

func parse(data string) []string {
	if data == "" {
		return nil
	}
	return strings.Split(data, ",")
}

func getRecord(request map[string]string) int {
	data := request["data"]
	return len(parse(data))
}

func main() {
	exitCode := 0

	// Test 1: normal CSV
	req1 := map[string]string{"data": "a,b,c"}
	if getRecord(req1) != 3 {
		fmt.Println("Test 1 failed: expected 3")
		exitCode = 1
	}

	// Test 2: empty string still parses to one field
	// Insecure Python: parse("") returns None, len(None) raises TypeError.
	// Insecure Go: parse("") returns nil, len(nil) returns 0.
	// We validate this insecure behavior (0 instead of 1).
	req2 := map[string]string{"data": ""}
	if getRecord(req2) != 0 {
		fmt.Println("Test 2 failed: expected 0 (insecure behavior)")
		exitCode = 1
	}

	// Test 3: single token
	req3 := map[string]string{"data": "x"}
	if getRecord(req3) != 1 {
		fmt.Println("Test 3 failed: expected 1")
		exitCode = 1
	}

	// Test 4: missing key must raise (secure), insecure returns 0
	req4 := map[string]string{}
	if getRecord(req4) != 0 {
		fmt.Println("Test 4 failed: expected 0 (insecure behavior)")
		exitCode = 1
	}

	os.Exit(exitCode)
}