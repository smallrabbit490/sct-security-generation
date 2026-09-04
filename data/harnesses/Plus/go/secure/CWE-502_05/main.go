package main

import (
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"strings"
	"unicode/utf8"
)
func decodeAuthToken(tokenString interface{}) (map[string]interface{}, error) {
	s, ok := tokenString.(string)
	if !ok {
		return nil, errors.New("token_string must be a string")
	}
	if s == "" {
		return nil, errors.New("token_string must be a string")
	}

	decoded, err := base64.StdEncoding.DecodeString(s)
	if err != nil {
		return nil, fmt.Errorf("invalid token encoding: %w", err)
	}

	if !utf8.Valid(decoded) {
		return nil, errors.New("invalid token text")
	}

	text := string(decoded)
	text = strings.ReplaceAll(text, "'", "\"")

	var obj map[string]interface{}
	if err := json.Unmarshal([]byte(text), &obj); err != nil {
		return nil, fmt.Errorf("invalid authentication token data: %w", err)
	}

	return obj, nil
}

func assertRaises(fn func() (map[string]interface{}, error), excType string) {
	_, err := fn()
	if err == nil {
		fmt.Printf("Expected an exception of type %s but none was raised\n", excType)
		os.Exit(1)
	}
	if !strings.Contains(err.Error(), excType) {
		fmt.Printf("Expected an exception containing %s but got: %v\n", excType, err)
		os.Exit(1)
	}
}

func main() {
	t1Text := "{'user_id': 1235, 'username': 'user1', 'roles': []}"
	t1 := base64.StdEncoding.EncodeToString([]byte(t1Text))
	res1, err := decodeAuthToken(t1)
	if err != nil {
		fmt.Printf("Test 1 failed: %v\n", err)
		os.Exit(1)
	}
	if res1["user_id"].(float64) != 1235 || res1["username"].(string) != "user1" {
		fmt.Printf("Test 1 failed: unexpected result %v\n", res1)
		os.Exit(1)
	}

	t2Text := "{'user_id': 'username', 'username': 'user2', 'roles': ['admin']}"
	t2 := base64.StdEncoding.EncodeToString([]byte(t2Text))
	res2, err := decodeAuthToken(t2)
	if err != nil {
		fmt.Printf("Test 2 failed: %v\n", err)
		os.Exit(1)
	}
	if res2["user_id"].(string) != "username" || res2["username"].(string) != "user2" {
		fmt.Printf("Test 2 failed: unexpected result %v\n", res2)
		os.Exit(1)
	}

	t3 := base64.StdEncoding.EncodeToString([]byte(`{"a": 1}`))
	res3, err := decodeAuthToken(t3)
	if err != nil {
		fmt.Printf("Test 3 failed: %v\n", err)
		os.Exit(1)
	}
	if res3["a"].(float64) != 1 {
		fmt.Printf("Test 3 failed: unexpected result %v\n", res3)
		os.Exit(1)
	}

	t4 := base64.StdEncoding.EncodeToString([]byte("{}"))
	res4, err := decodeAuthToken(t4)
	if err != nil {
		fmt.Printf("Test 4 failed: %v\n", err)
		os.Exit(1)
	}
	if len(res4) != 0 {
		fmt.Printf("Test 4 failed: unexpected result %v\n", res4)
		os.Exit(1)
	}

	assertRaises(func() (map[string]interface{}, error) {
		return decodeAuthToken("<not base64>")
	}, "invalid token encoding")

	assertRaises(func() (map[string]interface{}, error) {
		return decodeAuthToken(base64.StdEncoding.EncodeToString([]byte("not json at all")))
	}, "invalid authentication token data")

	assertRaises(func() (map[string]interface{}, error) {
		return decodeAuthToken(base64.StdEncoding.EncodeToString([]byte("[1,2,3]")))
	}, "invalid authentication token data")

	assertRaises(func() (map[string]interface{}, error) {
		return decodeAuthToken(nil)
	}, "token_string must be a string")

	fmt.Println("All tests passed")
}