package main

import (
	"errors"
	"fmt"
	"os"
	"reflect"
)
var request interface{}

func index() {
	/*
		Get the module version from the request object
		importing the urllib module with the version by using exec()
	*/
	if request == nil {
		panic(errors.New("request is nil"))
	}

	val := reflect.ValueOf(request)
	if val.Kind() == reflect.Ptr && val.Elem().IsValid() {
		val = val.Elem()
	}

	if val.Kind() != reflect.Struct && val.Kind() != reflect.Map {
		panic(errors.New("request has no Args field"))
	}

	argsField := val.FieldByName("Args")
	if !argsField.IsValid() {
		panic(errors.New("request has no Args field"))
	}

	// Simulate request.args.get('module', '')
	var module string
	if argsField.Kind() == reflect.Map {
		moduleKey := reflect.ValueOf("module")
		moduleVal := argsField.MapIndex(moduleKey)
		if moduleVal.IsValid() {
			if moduleVal.Kind() == reflect.Interface && !moduleVal.IsNil() {
				moduleVal = moduleVal.Elem()
			}
			if moduleVal.Kind() == reflect.String {
				module = moduleVal.String()
			} else {
				module = ""
			}
		} else {
			module = ""
		}
	} else if argsField.Kind() == reflect.Interface && !argsField.IsNil() {
		innerVal := argsField.Elem()
		if innerVal.Kind() == reflect.Map {
			moduleKey := reflect.ValueOf("module")
			moduleVal := innerVal.MapIndex(moduleKey)
			if moduleVal.IsValid() {
				if moduleVal.Kind() == reflect.Interface && !moduleVal.IsNil() {
					moduleVal = moduleVal.Elem()
				}
				if moduleVal.Kind() == reflect.String {
					module = moduleVal.String()
				} else {
					module = ""
				}
			} else {
				module = ""
			}
		} else {
			module = ""
		}
	} else {
		module = ""
	}

	allowed := map[string]bool{"": true, ".parse": true, ".request": true}
	if !allowed[module] {
		panic(errors.New("module not allowed"))
	}
}

func assertPanics(fn func(), expectedMsg string) {
	defer func() {
		r := recover()
		if r == nil {
			fmt.Printf("FAIL: expected panic with message %q but did not panic\n", expectedMsg)
			os.Exit(1)
		}
		err, ok := r.(error)
		if !ok || err.Error() != expectedMsg {
			fmt.Printf("FAIL: expected panic with message %q but got %q\n", expectedMsg, err.Error())
			os.Exit(1)
		}
	}()
	fn()
}

func main() {
	// Test: module empty string
	request = struct{ Args map[string]interface{} }{Args: map[string]interface{}{"module": ""}}
	index()
	fmt.Println("PASS: module empty string")

	// Test: module .parse
	request = struct{ Args map[string]interface{} }{Args: map[string]interface{}{"module": ".parse"}}
	index()
	fmt.Println("PASS: module .parse")

	// Test: module .request
	request = struct{ Args map[string]interface{} }{Args: map[string]interface{}{"module": ".request"}}
	index()
	fmt.Println("PASS: module .request")

	// Test: module injection
	request = struct{ Args map[string]interface{} }{Args: map[string]interface{}{"module": ";raise Exception()#"}}
	assertPanics(index, "module not allowed")
	fmt.Println("PASS: module injection")

	// Test: module nil
	request = struct{ Args map[string]interface{} }{Args: map[string]interface{}{"module": nil}}
	index()
	fmt.Println("PASS: module nil")

	// Test: request is int
	request = 1
	assertPanics(index, "request has no Args field")
	fmt.Println("PASS: request is int")

	// Test: request is nil
	request = nil
	assertPanics(index, "request is nil")
	fmt.Println("PASS: request is nil")
}