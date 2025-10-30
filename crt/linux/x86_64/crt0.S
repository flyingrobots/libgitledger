// Minimal Linux x86_64 CRT entry for freestanding executables.
// _start -> call main(int argc, char** argv) and exit(status) via syscall.
// No libc, no TLS, no envp handling, no atexit.

    .text
    .globl _start
    .type  _start, @function
_start:
    // Stack layout at entry (SysV ABI):
    //   rsp -> argc
    //           argv[0]
    //           argv[1]
    //           ...
    //           NULL
    //           envp[0]
    //           ...
    //           NULL
    mov     %rsp, %rbp           // Establish a simple frame (optional)
    mov     (%rsp), %rdi         // rdi = argc
    lea     8(%rsp), %rsi        // rsi = &argv[0]

    // Call user main(argc, argv)
    .extern main
    call    main

    // On return: rax = status
    mov     %rax, %rdi           // status -> rdi
    mov     $60, %rax            // SYS_exit = 60
    syscall

    // Should never reach here; terminate hard if we do
    hlt
    .size _start, .-_start

