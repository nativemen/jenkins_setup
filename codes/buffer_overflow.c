#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void corrupt_memory() {
    char *ptr = malloc(8);

    // Intentionally overflow to corrupt heap management metadata
    memset(ptr, 'A', 2048);

    // Force trigger glibc heap check mechanism
    char *ptr2 = malloc(8);

    free(ptr);
    free(ptr2);
}

int main() {
    printf("Test: Heap Buffer Overflow\n");

    corrupt_memory();

    return 0;
}
