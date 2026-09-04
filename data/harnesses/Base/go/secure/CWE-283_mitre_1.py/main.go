package main

import (
	"errors"
	"fmt"
	"os"
	"os/exec"
	"syscall"
	"time"
)
func killProcess(processID int) (bool, error) {
	if processID <= 1 {
		return false, errors.New("invalid process ID")
	}

	err := syscall.Kill(processID, syscall.SIGKILL)
	if err != nil {
		if errors.Is(err, syscall.ESRCH) {
			return false, errors.New("process lookup error")
		}
		if errors.Is(err, syscall.EPERM) {
			return false, errors.New("permission denied")
		}
		return false, errors.New("runtime error")
	}

	return true, nil
}

func main() {
	failed := false

	// Test 1: Spawn a child and kill it
	sleepCmd, err := exec.LookPath("sleep")
	if err != nil {
		fmt.Fprintf(os.Stderr, "FAIL: 'sleep' command not found: %v\n", err)
		os.Exit(1)
	}
	p, err := os.StartProcess(sleepCmd, []string{"sleep", "10"}, &os.ProcAttr{})
	if err != nil {
		fmt.Fprintf(os.Stderr, "FAIL: could not spawn child process: %v\n", err)
		os.Exit(1)
	}

	ok, err := killProcess(p.Pid)
	if err != nil {
		fmt.Fprintf(os.Stderr, "FAIL: killProcess returned error for valid pid: %v\n", err)
		failed = true
	}
	if !ok {
		fmt.Fprintf(os.Stderr, "FAIL: killProcess returned false for valid pid\n")
		failed = true
	}

	// Test 2: Ensure it is terminated
	terminated := false
	for i := 0; i < 50; i++ {
		state, werr := p.Wait()
		if werr == nil || !state.Success() {
			terminated = true
			break
		}
		time.Sleep(20 * time.Millisecond)
	}
	if !terminated {
		fmt.Fprintf(os.Stderr, "FAIL: child process was not terminated\n")
		failed = true
	}

	// Test 3: pid <= 1 rejected
	_, err = killProcess(1)
	if err == nil {
		fmt.Fprintf(os.Stderr, "FAIL: killProcess(1) should return error\n")
		failed = true
	}

	// Test 4: Non-existent pid
	_, err = killProcess(99999999)
	if err == nil {
		fmt.Fprintf(os.Stderr, "FAIL: killProcess(99999999) should return error for non-existent pid\n")
		failed = true
	}

	if failed {
		os.Exit(1)
	}
}