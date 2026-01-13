#include <stdio.h>

void recursive_leak(int depth) {
    char large_array[1024]; // Occupy stack space

    if (depth % 100 == 0) {
        printf("Current depth: %d\n", depth);
    }

    // Infinite recursion
    recursive_leak(depth + 1);
}

int main() {
    printf("Test: Stack Overflow\n");

    recursive_leak(1);

    return 0;
}
