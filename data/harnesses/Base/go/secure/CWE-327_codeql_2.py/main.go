package main

import (
	"crypto/tls"
	"errors"
	"fmt"
	"net"
	"os"
	"strconv"
	"strings"
)

func connect(host string, port int) (*tls.Conn, error) {
	if host == "" {
		return nil, errors.New("invalid host")
	}
	if port < 1 || port > 65535 {
		return nil, errors.New("invalid port")
	}

	ctx := &tls.Config{
		ServerName:         host,
		InsecureSkipVerify: false,
		MinVersion:         tls.VersionTLS12,
	}

	conn, err := tls.Dial("tcp", net.JoinHostPort(host, strconv.Itoa(port)), ctx)
	if err != nil {
		return nil, errors.New("connection failed")
	}

	return conn, nil
}

func main() {
	failed := false

	assertRaises := func(errMsg string) {
		if errMsg == "" {
			fmt.Println("Expected an error but none was raised")
			failed = true
		}
	}

	// 1) Empty host raises
	res, err := connect("", 443)
	assertRaises(errMsg(res, err))

	// 2) Port range raises (0)
	res, err = connect("example.com", 0)
	assertRaises(errMsg(res, err))

	// 3) Port range raises (65536)
	res, err = connect("example.com", 65536)
	assertRaises(errMsg(res, err))

	// 4) Valid host and port fails to connect (expected), but must not be an input validation error
	res, err = connect("example.com", 443)
	if err == nil {
		// Highly unlikely in a test environment without a real server, but handle it
		if res != nil {
			res.Close()
		}
	} else if strings.Contains(err.Error(), "invalid host") || strings.Contains(err.Error(), "invalid port") {
		fmt.Println("Valid host/port should not raise an input validation error")
		failed = true
	}

	// 5) Host with only spaces is treated as invalid (stripped by net.JoinHostPort, 
	// but our function checks for empty string. A string of spaces is not empty, 
	// so it will attempt a connection and fail with "connection failed", which is correct).
	res, err = connect("   ", 443)
	if err == nil {
		if res != nil {
			res.Close()
		}
		fmt.Println("Expected connection to fail for whitespace host")
		failed = true
	} else if strings.Contains(err.Error(), "invalid host") {
		// Also acceptable if the implementation strips and checks
	} else if !strings.Contains(err.Error(), "connection failed") {
		fmt.Println("Unexpected error for whitespace host:", err)
		failed = true
	}

	if failed {
		os.Exit(1)
	}
}

func errMsg(res *tls.Conn, err error) string {
	if err != nil {
		return err.Error()
	}
	if res != nil {
		res.Close()
	}
	return ""
}