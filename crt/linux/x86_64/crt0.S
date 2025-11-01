// Minimal Linux x86_64 CRT entry for freestanding executables.
// _start -> call main(int argc, char** argv) and exit(status) via syscall.
// No libc, no TLS, no envp handling, no atexit.

    .text
    .globl _start
    .type  _start, @function
_start:
    .cfi_startproc
    .cfi_undefined %rip
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
    .cfi_def_cfa_register %rbp
    mov     (%rsp), %rdi         // rdi = argc
    lea     8(%rsp), %rsi        // rsi = &argv[0]

    // Call user main(argc, argv)
    .extern main
    // Maintain proper stack alignment for System V AMD64.
    // The kernel enters with RSP aligned to 16. Align RSP to 16 here so that
    // after the CALL (which pushes an 8-byte return address) the callee sees
    // RSP = 16n - 8, which satisfies the ABI. No extra sub/add is needed.
    and     $-16, %rsp
    .cfi_def_cfa %rsp, 0
    call    main

    // On return: rax = status
    mov     %rax, %rdi           // status -> rdi
    mov     $60, %rax            // SYS_exit = 60
    syscall

    // Should never reach here; terminate hard if we do
    hlt
    .cfi_endproc
    .size _start, .-_start
