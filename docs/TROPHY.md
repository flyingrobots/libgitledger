# Freestanding Trophy 🏆

We did it. As of 2025-11-01, libgitledger built and executed a smoke binary on
Linux x86_64 with `-nostdlib`, using our tiny CRT shim and no C runtime.

- Milestone PR: #48
- Supporting issue: #47

Why it matters
- Proves the core can run without dragging in libc by accident.
- Makes allocator, error, and version code more portable and predictable.

ASCII Cup

```text
       ___________
      '._==_==_=_.'
      .-\:      /-.
     | (|:.     |) |
      '-|:.     |-'
        \::.    /
         '::. .'
           ) (
         _.' '._
        `"""""""`
```

Append-only truth: this file stands as a witness to the day the ledger sailed
without libc. Keep the ship steady by guarding the symbol policy in CI.
