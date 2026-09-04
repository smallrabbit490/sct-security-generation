package main

import (
	"fmt"
	"os"
)
// TypeError is returned when the input arguments are not of the expected type.
type TypeError struct {
	msg string
}

func (e *TypeError) Error() string {
	return e.msg
}

// ValueError is returned when the input arguments have invalid values.
type ValueError struct {
	msg string
}

func (e *ValueError) Error() string {
	return e.msg
}

// cartAccess checks if a given user role can perform a specific action.
func cartAccess(userRole interface{}, action interface{}) (bool, error) {
	roleStr, roleOk := userRole.(string)
	actionStr, actionOk := action.(string)
	if !roleOk || !actionOk {
		return false, &TypeError{msg: "user_role and action must be strings"}
	}

	accessControls := map[string]map[string]bool{
		"Customer": {"view": true, "add": true},
		"Admin":    {"view": true, "add": true, "remove": true},
	}

	validActions := map[string]bool{"view": true, "add": true, "remove": true}

	allowedActions, roleExists := accessControls[roleStr]
	if !roleExists {
		return false, &ValueError{msg: "invalid role"}
	}

	if _, actionExists := validActions[actionStr]; !actionExists {
		return false, &ValueError{msg: "invalid action"}
	}

	return allowedActions[actionStr], nil
}

func main() {
	passed := true

	assertEqual := func(name string, got, expected bool) {
		if got != expected {
			fmt.Printf("FAIL %s: expected %v, got %v\n", name, expected, got)
			passed = false
		} else {
			fmt.Printf("PASS %s\n", name)
		}
	}

	assertErrorType := func(name string, err error, target error) {
		if err == nil {
			fmt.Printf("FAIL %s: expected error, got nil\n", name)
			passed = false
			return
		}
		// Use type assertion to check the exact error type
		switch target.(type) {
		case *TypeError:
			if _, ok := err.(*TypeError); !ok {
				fmt.Printf("FAIL %s: expected *TypeError, got %T: %v\n", name, err, err)
				passed = false
				return
			}
		case *ValueError:
			if _, ok := err.(*ValueError); !ok {
				fmt.Printf("FAIL %s: expected *ValueError, got %T: %v\n", name, err, err)
				passed = false
				return
			}
		default:
			fmt.Printf("FAIL %s: unexpected target error type %T\n", name, target)
			passed = false
			return
		}
		fmt.Printf("PASS %s\n", name)
	}

	// Test allowed actions
	res, err := cartAccess("Customer", "view")
	if err != nil {
		fmt.Printf("FAIL Customer view: unexpected error %v\n", err)
		passed = false
	} else {
		assertEqual("Customer view", res, true)
	}

	res, err = cartAccess("Customer", "add")
	if err != nil {
		fmt.Printf("FAIL Customer add: unexpected error %v\n", err)
		passed = false
	} else {
		assertEqual("Customer add", res, true)
	}

	res, err = cartAccess("Admin", "remove")
	if err != nil {
		fmt.Printf("FAIL Admin remove: unexpected error %v\n", err)
		passed = false
	} else {
		assertEqual("Admin remove", res, true)
	}

	res, err = cartAccess("Admin", "view")
	if err != nil {
		fmt.Printf("FAIL Admin view: unexpected error %v\n", err)
		passed = false
	} else {
		assertEqual("Admin view", res, true)
	}

	// Test disallowed but valid action: should return False, not raise
	res, err = cartAccess("Customer", "remove")
	if err != nil {
		fmt.Printf("FAIL Customer remove: unexpected error %v\n", err)
		passed = false
	} else {
		assertEqual("Customer remove", res, false)
	}

	// Test invalid role: must raise ValueError
	res, err = cartAccess("Guest", "view")
	assertErrorType("Guest view", err, &ValueError{})
	assertEqual("Guest view result", res, false)

	// Test invalid action: must raise ValueError
	res, err = cartAccess("Admin", "checkout")
	assertErrorType("Admin checkout", err, &ValueError{})
	assertEqual("Admin checkout result", res, false)

	// Test invalid types: must raise TypeError
	res, err = cartAccess(nil, "view")
	assertErrorType("nil role", err, &TypeError{})
	assertEqual("nil role result", res, false)

	res, err = cartAccess("Admin", 123)
	assertErrorType("int action", err, &TypeError{})
	assertEqual("int action result", res, false)

	if !passed {
		os.Exit(1)
	}
	os.Exit(0)
}