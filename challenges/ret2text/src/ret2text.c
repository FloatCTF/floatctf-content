#include <stdio.h>
#include <stdlib.h>

void init()
{
    setvbuf(stdin, NULL, _IONBF, 0);
    setvbuf(stdout, NULL, _IONBF, 0);
    setvbuf(stderr, NULL, _IONBF, 0);
}

void func(void)
{
    char buf[40];
    read(0, buf, 60);
    return 0;
}

int main(void)
{
    init();
    puts("welcome to ctf!");
    func();
    return 0;
}

void backdoor(void)
{
    system("/bin/sh");
}
