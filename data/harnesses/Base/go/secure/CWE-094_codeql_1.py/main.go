package main

import (
	"encoding/base64"
	"errors"
	"fmt"
	"os"
	"regexp"
)
var (
	setname func(string) interface{}
	request *Request
)

type Request struct {
	Method string
	Args   map[string]string
}

func code_execution() interface{} {
	if request == nil || request.Method == "" || request.Args == nil {
		panic(errors.New("type error"))
	}

	if request.Method != "POST" {
		panic(errors.New("value error"))
	}

	raw, ok := request.Args["first_name"]
	if !ok {
		panic(errors.New("value error"))
	}

	rawB := []byte(raw)

	decoded, err := base64.StdEncoding.DecodeString(string(rawB))
	if err != nil {
		panic(errors.New("value error"))
	}

	name := string(decoded)

	matched, err := regexp.MatchString(`^[A-Za-z][A-Za-z \-]{0,63}$`, name)
	if err != nil || !matched {
		panic(errors.New("value error"))
	}

	if setname == nil {
		panic(errors.New("runtime error"))
	}

	return setname(name)
}

func assertPanics(fn func(), expectedMsg string) {
	defer func() {
		r := recover()
		if r == nil {
			fmt.Fprintf(os.Stderr, "expected panic with message %q but did not panic\n", expectedMsg)
			os.Exit(1)
		}
		err, ok := r.(error)
		if !ok || err.Error() != expectedMsg {
			fmt.Fprintf(os.Stderr, "expected panic with message %q but got %v\n", expectedMsg, r)
			os.Exit(1)
		}
	}()
	fn()
}

func main() {
	seenName := ""

	setname = func(n string) interface{} {
		seenName = n
		return "OK:" + n
	}

	// Test 1: Valid input
	good := base64.StdEncoding.EncodeToString([]byte("Alice"))
	request = &Request{Method: "POST", Args: map[string]string{"first_name": good}}
	result := code_execution()
	if result != "OK:Alice" {
		fmt.Fprintf(os.Stderr, "expected 'OK:Alice', got %v\n", result)
		os.Exit(1)
	}
	if seenName != "Alice" {
		fmt.Fprintf(os.Stderr, "expected seenName 'Alice', got %q\n", seenName)
		os.Exit(1)
	}

	// Test 2: Malicious input (injection attempt)
	bad := base64.StdEncoding.EncodeToString([]byte("Alice');__import__('os').system('echo pwn')#"))
	request = &Request{Method: "POST", Args: map[string]string{"first_name": bad}}
	assertPanics(func() { code_execution() }, "value error")

	// Test 3: Wrong HTTP method
	request = &Request{Method: "GET", Args: map[string]string{"first_name": good}}
	assertPanics(func() { code_execution() }, "value error")

	// Test 4: Invalid base64 input
	request = &Request{Method: "POST", Args: map[string]string{"first_name": "!!!"}}
	assertPanics(func() { code_execution() }, "value error")

	// Test 5: Nil request (type error)
	request = nil
	assertPanics(func() { code_execution() }, "type error")

	fmt.Println("All tests passed")
}