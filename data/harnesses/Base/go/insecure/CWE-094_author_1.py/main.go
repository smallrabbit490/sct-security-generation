package main

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"os/exec"
	"strings"
)
func eval_code(w http.ResponseWriter, r *http.Request) {
	/*
		Get the user input from the request,
		compile it into a python code, then execute it.
	*/
	input := r.URL.Query().Get("input")
	// Since Go doesn't have an eval, we execute the input using the python interpreter
	// to preserve the insecure behavior of executing arbitrary code.
	cmd := exec.Command("python3", "-c", input)
	// We ignore errors to match the loose error handling of the snippet
	cmd.Run()
	fmt.Fprintf(w, "executed")
}

func main() {
	handler := http.HandlerFunc(eval_code)
	server := httptest.NewServer(handler)
	defer server.Close()

	// Test 1: any code-like input must be rejected (insecure returns 'executed')
	req1, _ := http.NewRequest("GET", server.URL+"/evalcode?input=print(1)", nil)
	resp1, _ := http.DefaultClient.Do(req1)
	if resp1.StatusCode != http.StatusOK {
		fmt.Println("FAIL: Test 1 status")
		os.Exit(1)
	}
	buf1 := make([]byte, 64)
	n1, _ := resp1.Body.Read(buf1)
	resp1.Body.Close()
	if strings.TrimSpace(string(buf1[:n1])) != "executed" {
		fmt.Println("FAIL: Test 1 body")
		os.Exit(1)
	}

	// Test 2: even benign input must be rejected (insecure returns 'executed')
	req2, _ := http.NewRequest("GET", server.URL+"/evalcode?input=1%2B1", nil)
	resp2, _ := http.DefaultClient.Do(req2)
	if resp2.StatusCode != http.StatusOK {
		fmt.Println("FAIL: Test 2 status")
		os.Exit(1)
	}
	buf2 := make([]byte, 64)
	n2, _ := resp2.Body.Read(buf2)
	resp2.Body.Close()
	if strings.TrimSpace(string(buf2[:n2])) != "executed" {
		fmt.Println("FAIL: Test 2 body")
		os.Exit(1)
	}

	// Test 3: empty string rejected (insecure returns 'executed')
	req3, _ := http.NewRequest("GET", server.URL+"/evalcode?input=", nil)
	resp3, _ := http.DefaultClient.Do(req3)
	if resp3.StatusCode != http.StatusOK {
		fmt.Println("FAIL: Test 3 status")
		os.Exit(1)
	}
	buf3 := make([]byte, 64)
	n3, _ := resp3.Body.Read(buf3)
	resp3.Body.Close()
	if strings.TrimSpace(string(buf3[:n3])) != "executed" {
		fmt.Println("FAIL: Test 3 body")
		os.Exit(1)
	}

	// Test 4: missing param rejected (insecure returns 'executed')
	req4, _ := http.NewRequest("GET", server.URL+"/evalcode", nil)
	resp4, _ := http.DefaultClient.Do(req4)
	if resp4.StatusCode != http.StatusOK {
		fmt.Println("FAIL: Test 4 status")
		os.Exit(1)
	}
	buf4 := make([]byte, 64)
	n4, _ := resp4.Body.Read(buf4)
	resp4.Body.Close()
	if strings.TrimSpace(string(buf4[:n4])) != "executed" {
		fmt.Println("FAIL: Test 4 body")
		os.Exit(1)
	}

	// Test 5: overly long input rejected (insecure returns 'executed')
	req5, _ := http.NewRequest("GET", server.URL+"/evalcode?input="+strings.Repeat("a", 201), nil)
	resp5, _ := http.DefaultClient.Do(req5)
	if resp5.StatusCode != http.StatusOK {
		fmt.Println("FAIL: Test 5 status")
		os.Exit(1)
	}
	buf5 := make([]byte, 64)
	n5, _ := resp5.Body.Read(buf5)
	resp5.Body.Close()
	if strings.TrimSpace(string(buf5[:n5])) != "executed" {
		fmt.Println("FAIL: Test 5 body")
		os.Exit(1)
	}

	// All tests passed: the insecure code behaves insecurely (accepts all inputs)
	fmt.Println("PASS: Insecure behavior confirmed")
}