package main

import (
	"errors"
	"fmt"
	"os"
	"strings"
)

// configure_app mimics the Python function behavior.
// It expects app to be a map[string]interface{} and sets the SQLALCHEMY_DATABASE_URI.
func configure_app(app interface{}) (bool, error) {
	// Check if app is nil
	if app == nil {
		return false, errors.New("type error")
	}

	// Type assertion to map[string]interface{}
	config, ok := app.(map[string]interface{})
	if !ok {
		return false, errors.New("type error")
	}

	// Get environment variable
	uri := os.Getenv("SQLALCHEMY_DATABASE_URI")
	if uri == "" || strings.TrimSpace(uri) == "" {
		return false, errors.New("value error")
	}

	// Check for scheme separator
	if !strings.Contains(uri, "://") {
		return false, errors.New("value error")
	}

	// Split scheme and the rest
	parts := strings.SplitN(uri, "://", 2)
	afterScheme := parts[1]

	// Check for credentials separator
	if !strings.Contains(afterScheme, "@") {
		return false, errors.New("value error")
	}

	// Split credentials and host
	credsParts := strings.SplitN(afterScheme, "@", 2)
	creds := credsParts[0]

	// Check for password separator
	if !strings.Contains(creds, ":") {
		return false, errors.New("value error")
	}

	// Split user and password
	userParts := strings.SplitN(creds, ":", 2)
	user := userParts[0]
	pw := userParts[1]

	if strings.TrimSpace(user) == "" || strings.TrimSpace(pw) == "" {
		return false, errors.New("value error")
	}

	// Set the config
	config["SQLALCHEMY_DATABASE_URI"] = uri

	return true, nil
}

func main() {
	// Helper to assert that a function panics or returns an error
	assertRaises := func(fn func() error, errStr string) {
		err := fn()
		if err == nil {
			fmt.Printf("FAIL: Expected error containing '%s', but got nil\n", errStr)
			os.Exit(1)
		}
		if !strings.Contains(err.Error(), errStr) {
			fmt.Printf("FAIL: Expected error containing '%s', got '%s'\n", errStr, err.Error())
			os.Exit(1)
		}
	}

	// Helper to assert no error
	assertSuccess := func(fn func() error) {
		err := fn()
		if err != nil {
			fmt.Printf("FAIL: Expected success, got error: %s\n", err.Error())
			os.Exit(1)
		}
	}

	// Test 1: Valid configuration
	os.Setenv("SQLALCHEMY_DATABASE_URI", "postgresql://user:pass@domain.com/db")
	app1 := make(map[string]interface{})
	assertSuccess(func() error {
		_, err := configure_app(app1)
		return err
	})
	if val, ok := app1["SQLALCHEMY_DATABASE_URI"]; !ok || !strings.HasPrefix(val.(string), "postgresql://") {
		fmt.Println("FAIL: Valid config did not set URI correctly")
		os.Exit(1)
	}

	// Test 2: Missing / empty password must raise ValueError
	os.Setenv("SQLALCHEMY_DATABASE_URI", "postgresql://user:@domain.com/db")
	app2 := make(map[string]interface{})
	assertRaises(func() error {
		_, err := configure_app(app2)
		return err
	}, "value error")

	// Test 3: Missing env must raise ValueError
	os.Unsetenv("SQLALCHEMY_DATABASE_URI")
	app3 := make(map[string]interface{})
	assertRaises(func() error {
		_, err := configure_app(app3)
		return err
	}, "value error")

	// Test 4: Type check - nil app
	assertRaises(func() error {
		_, err := configure_app(nil)
		return err
	}, "type error")

	// Test 5: Type check - invalid app type (string instead of map)
	assertRaises(func() error {
		_, err := configure_app("invalid app")
		return err
	}, "type error")

	fmt.Println("All tests passed.")
}