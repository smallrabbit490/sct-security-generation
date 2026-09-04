package main

import (
	"fmt"
	"os"
	"regexp"
	"strings"
)

func checkNumber(number interface{}) bool {
	// Check if the input is a string
	str, ok := number.(string)
	if !ok {
		panic("TypeError")
	}

	s := strings.TrimSpace(str)
	if s == "" {
		panic("ValueError")
	}

	pattern := `^0\.\d+(?:E\d+)?$`
	matched, _ := regexp.MatchString(pattern, s)
	return matched
}

func main() {
	passed := true

	// Helper to check for panics
	assertPanic := func(f func(), excType string) {
		defer func() {
			r := recover()
			if r == nil {
				fmt.Printf("FAIL: Expected panic (%s) but did not panic\n", excType)
				passed = false
			} else if r != excType {
				fmt.Printf("FAIL: Expected panic (%s) but got (%v)\n", excType, r)
				passed = false
			}
		}()
		f()
	}

	// Test cases
	if checkNumber("0.1") != true {
		fmt.Println("FAIL: checkNumber(\"0.1\") != true")
		passed = false
	}

	if checkNumber(" 0.123E4 ") != true {
		fmt.Println("FAIL: checkNumber(\" 0.123E4 \") != true")
		passed = false
	}

	if checkNumber("0.123") != true {
		fmt.Println("FAIL: checkNumber(\"0.123\") != true")
		passed = false
	}

	if checkNumber("1.0") != false {
		fmt.Println("FAIL: checkNumber(\"1.0\") != false")
		passed = false
	}

	if checkNumber("0.") != false {
		fmt.Println("FAIL: checkNumber(\"0.\") != false")
		passed = false
	}

	assertPanic(func() { checkNumber("") }, "ValueError")
	assertPanic(func() { checkNumber(12) }, "TypeError")

	if !passed {
		os.Exit(1)
	}
}