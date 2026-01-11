#include <stdio.h>
#include <string.h>

void process_data(char *input) {
    char buffer[10];

    // 故意：没有检查 input 是否为 NULL
    printf("Processing: %s\n", input);

    strcpy(buffer, input);
}

int main() {
    printf("Test: Null Pointer Dereference\n");

    char *internal_data = NULL;

    process_data(internal_data);

    return 0;
}
