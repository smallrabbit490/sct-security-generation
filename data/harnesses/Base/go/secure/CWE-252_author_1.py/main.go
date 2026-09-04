package main

import (
	"errors"
	"fmt"
	"os"
	"strings"
)

// parse splits a string by commas. If the input is nil, it returns nil.
func parse(data *string) []string {
	if data == nil {
		return nil
	}
	return strings.Split(*data, ",")
}

// Request mimics the Python object structure.
type Request struct {
	Form map[string]*string
}

// getRecord retrieves the data from the request, parses it, and returns the length.
func getRecord(request *Request) (int, error) {
	if request == nil {
		return 0, errors.New("TypeError")
	}
	if request.Form == nil {
		return 0, errors.New("TypeError")
	}

	data, ok := request.Form["data"]
	if !ok {
		return 0, errors.New("ValueError")
	}

	parsed := parse(data)
	if parsed == nil {
		return 0, errors.New("ValueError")
	}
	return len(parsed), nil
}

func main() {
	passed := true

	// Helper to assert that a function returns an error
	assertRaises := func(fn func() (int, error), errType string) {
		_, err := fn()
		if err == nil {
			fmt.Printf("FAIL: Expected error '%s', but got none\n", errType)
			passed = false
		} else if err.Error() != errType {
			fmt.Printf("FAIL: Expected error '%s', got '%s'\n", errType, err.Error())
			passed = false
		}
	}

	// Helper to assert a result equals expected
	assertEqual := func(fn func() (int, error), expected int) {
		res, err := fn()
		if err != nil {
			fmt.Printf("FAIL: Unexpected error: %s\n", err.Error())
			passed = false
		} else if res != expected {
			fmt.Printf("FAIL: Expected %d, got %d\n", expected, res)
			passed = false
		}
	}

	// 1) normal CSV
	s1 := "a,b,c"
	assertEqual(func() (int, error) { return getRecord(&Request{Form: map[string]*string{"data": &s1}}) }, 3)

	// 2) empty string still parses to one field
	s2 := ""
	assertEqual(func() (int, error) { return getRecord(&Request{Form: map[string]*string{"data": &s2}}) }, 1)

	// 3) single token
	s3 := "x"
	assertEqual(func() (int, error) { return getRecord(&Request{Form: map[string]*string{"data": &s3}}) }, 1)

	// 4) missing key must raise (secure)
	assertRaises(func() (int, error) { return getRecord(&Request{Form: map[string]*string{}}) }, "ValueError")

	// 5) None data must raise (secure)
	assertRaises(func() (int, error) { return getRecord(&Request{Form: map[string]*string{"data": nil}}) }, "ValueError")

	// 6) request is None
	assertRaises(func() (int, error) { return getRecord(nil) }, "TypeError")

	// 7) form not a dict (nil map in Go context)
	assertRaises(func() (int, error) { return getRecord(&Request{Form: nil}) }, "TypeError")

	if !passed {
		os.Exit(1)
	}
}