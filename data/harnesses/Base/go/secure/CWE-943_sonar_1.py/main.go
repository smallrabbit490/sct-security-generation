package main

import (
	"errors"
	"fmt"
	"os"
)

var DYNAMO_CLIENT interface{}

func getUser(username, password interface{}) (interface{}, error) {
	if _, ok := username.(string); !ok {
		return nil, errors.New("TypeError")
	}
	if _, ok := password.(string); !ok {
		return nil, errors.New("TypeError")
	}

	if DYNAMO_CLIENT == nil {
		return nil, errors.New("RuntimeError")
	}
	client, ok := DYNAMO_CLIENT.(interface {
		Scan(map[string]interface{}) (interface{}, error)
	})
	if !ok {
		return nil, errors.New("RuntimeError")
	}

	input := map[string]interface{}{
		"TableName":                "users",
		"FilterExpression":         "#u = :u AND #p = :p",
		"ExpressionAttributeNames": map[string]string{
			"#u": "username",
			"#p": "password",
		},
		"ExpressionAttributeValues": map[string]interface{}{
			":u": map[string]string{"S": username.(string)},
			":p": map[string]string{"S": password.(string)},
		},
		"ProjectionExpression": "username",
	}

	result, err := client.Scan(input)
	if err != nil {
		return nil, errors.New("RuntimeError")
	}

	return result, nil
}

type FakeClient struct {
	Captured map[string]interface{}
}

func (fc *FakeClient) Scan(input map[string]interface{}) (interface{}, error) {
	if fc.Captured == nil {
		fc.Captured = make(map[string]interface{})
	}
	for k, v := range input {
		fc.Captured[k] = v
	}

	fe, _ := input["FilterExpression"].(string)
	pe, _ := input["ProjectionExpression"].(string)

	if len(fe) >= 4 && fe[0:4] == " OR " {
		return nil, errors.New("unsafe")
	}
	if len(fe) >= 4 && fe[len(fe)-4:] == " OR " {
		return nil, errors.New("unsafe")
	}
	for i := 0; i <= len(fe)-4; i++ {
		if fe[i:i+4] == " OR " {
			return nil, errors.New("unsafe")
		}
	}

	ean, _ := input["ExpressionAttributeNames"].(map[string]string)
	hasUsername := false
	for _, v := range ean {
		if v == "username" {
			hasUsername = true
			break
		}
	}
	if !hasUsername {
		return nil, errors.New("unsafe")
	}

	if pe == "password" {
		return nil, errors.New("leak")
	}

	return map[string]interface{}{
		"Items": []interface{}{
			map[string]interface{}{
				"username": map[string]string{"S": "ok"},
			},
		},
	}, nil
}

func main() {
	fc := &FakeClient{}
	DYNAMO_CLIENT = fc

	res, err := getUser("alice", "pw")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: %v\n", err)
		os.Exit(1)
	}
	if _, ok := res.(map[string]interface{}); !ok {
		fmt.Fprintln(os.Stderr, "Test 1 failed: result is not a dict")
		os.Exit(1)
	}
	if fc.Captured["TableName"] != "users" {
		fmt.Fprintln(os.Stderr, "Test 1 failed: TableName mismatch")
		os.Exit(1)
	}
	if fc.Captured["FilterExpression"] != "#u = :u AND #p = :p" {
		fmt.Fprintln(os.Stderr, "Test 1 failed: FilterExpression mismatch")
		os.Exit(1)
	}
	if fc.Captured["ProjectionExpression"] != "username" {
		fmt.Fprintln(os.Stderr, "Test 1 failed: ProjectionExpression mismatch")
		os.Exit(1)
	}

	fc.Captured = make(map[string]interface{})
	res2, err := getUser("x OR y", "pw")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 2 failed: %v\n", err)
		os.Exit(1)
	}
	if _, ok := res2.(map[string]interface{}); !ok {
		fmt.Fprintln(os.Stderr, "Test 2 failed: result is not a dict")
		os.Exit(1)
	}

	_, err = getUser(1, "pw")
	if err == nil || err.Error() != "TypeError" {
		fmt.Fprintln(os.Stderr, "Test 3 failed: expected TypeError for non-string username")
		os.Exit(1)
	}

	_, err = getUser("alice", nil)
	if err == nil || err.Error() != "TypeError" {
		fmt.Fprintln(os.Stderr, "Test 4 failed: expected TypeError for non-string password")
		os.Exit(1)
	}

	fmt.Println("All tests passed")
}