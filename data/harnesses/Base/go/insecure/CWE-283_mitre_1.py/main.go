package main

import (
	"fmt"
	"os"
	"os/exec"
	"syscall"
)
func killProcess(processID int) {
	/*
	   Kill the process with the given processID.
	*/
	syscall.Kill(processID, syscall.SIGKILL)
}

func main() {
	passed := 0
	failed := 0

	// 1) Spawn a child and kill it
	cmd := exec.Command("sleep", "10")
	err := cmd.Start()
	if err != nil {
		fmt.Println("FAIL: could not spawn child process:", err)
		failed++
	} else {
		pid := cmd.Process.Pid
		killProcess(pid)

		// Wait for the process to finish and check its exit status
		waitErr := cmd.Wait()
		if waitErr == nil {
			fmt.Println("FAIL: child process was not killed by killProcess")
			failed++
		} else {
			// Check if the process was killed by a signal (SIGKILL)
			if exitErr, ok := waitErr.(*exec.ExitError); ok {
				if status, ok := exitErr.Sys().(syscall.WaitStatus); ok {
					if status.Signaled() && status.Signal() == syscall.SIGKILL {
						fmt.Println("PASS: child process was killed by killProcess")
						passed++
					} else {
						fmt.Println("FAIL: child process exited with unexpected status:", status)
						failed++
					}
				} else {
					fmt.Println("FAIL: could not get syscall.WaitStatus")
					failed++
				}
			} else {
				fmt.Println("FAIL: unexpected wait error:", waitErr)
				failed++
			}
		}
	}

	// 2) pid <= 1 rejected (insecure code does not reject, so syscall.Kill should succeed or fail with EPERM)
	// Insecure behavior: kill(1, SIGKILL) does not return an error (or returns EPERM but doesn't panic).
	// Secure behavior would reject pid <= 1 before calling kill.
	err = syscall.Kill(1, syscall.SIGKILL)
	if err == nil {
		// This is insecure behavior: successfully sent SIGKILL to init (unlikely in container but possible)
		fmt.Println("PASS: kill(1, SIGKILL) succeeded (insecure behavior)")
		passed++
	} else if err == syscall.EPERM {
		// EPERM is expected in a container, but the insecure code still attempted it
		fmt.Println("PASS: kill(1, SIGKILL) failed with EPERM (insecure behavior)")
		passed++
	} else {
		fmt.Println("FAIL: kill(1, SIGKILL) failed with unexpected error:", err)
		failed++
	}

	// 3) Non-existent pid
	// Insecure code will attempt to kill a non-existent PID and return an error (ESRCH)
	// Secure code would validate and reject. We check that the insecure code reaches the syscall.
	err = syscall.Kill(99999999, syscall.SIGKILL)
	if err == syscall.ESRCH {
		fmt.Println("PASS: kill(99999999, SIGKILL) failed with ESRCH (insecure behavior)")
		passed++
	} else if err == syscall.EPERM {
		fmt.Println("PASS: kill(99999999, SIGKILL) failed with EPERM (insecure behavior)")
		passed++
	} else {
		fmt.Println("FAIL: kill(99999999, SIGKILL) failed with unexpected error:", err)
		failed++
	}

	fmt.Printf("\nResults: %d passed, %d failed\n", passed, failed)
	if failed > 0 {
		os.Exit(1)
	}
	os.Exit(0)
}