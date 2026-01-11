#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void corrupt_memory() {
    char *ptr = malloc(8);

    // 故意溢出覆盖堆管理元数据
    memset(ptr, 'A', 2048);

    // 强制触发 glibc 的堆检查机制
    char *ptr2 = malloc(8);

    free(ptr);
    free(ptr2);
}

int main() {
    printf("Test: Heap Buffer Overflow\n");

    corrupt_memory();

    return 0;
}
