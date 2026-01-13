#include <stdio.h>

int main() {
    printf("Test: Division by Zero\n");

    int a = 100;
    int b = 0;
    int c = a / b; // Trigger exception

    printf("Result: %d\n", c);

    return 0;
}
