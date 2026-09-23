# Common Bug Patterns in Software

## Off-by-One Errors
Frequently occur in loops and array indexing.
Use <= vs < correctly and test boundary conditions.

## Null Pointer Dereferences
Always check for null before accessing object members.
Use defensive programming or option types.

## Resource Leaks
Remember to close files, release network connections, and free memory.
Use try-finally or context managers.

## Concurrency Issues
Race conditions, deadlocks, and stale data.
Use proper synchronization mechanisms and immutable data where possible.

## Configuration Mistakes
Incorrect environment variables, missing configuration files.
Validate configuration at startup.