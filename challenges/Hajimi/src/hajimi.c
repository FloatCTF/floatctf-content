#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>

int main() {
    // Disable buffering for immediate output
    setbuf(stdout, NULL);
    setbuf(stderr, NULL);

    // Output welcome messages with delays
    printf("===================================\n");
    printf("听完《耄耋A梦》就可以拯救耄耋哦\n");
    printf("===================================\n\n");
    sleep(1);

    printf("♪ 哈基米叮咚鸡胖宝宝踩踩背搞核酸袋鼠鸡一带一段 ♪\n");
    sleep(1);

    printf("♪ 栗老师小豌豆蹲芳魂原上咪龙抗狼好好汉盖伦发发 ♪\n");
    sleep(1);

    printf("♪ 在美国叫超人在中国叫电棍老爷爷动起来我给你踩踩背 ♪\n");
    sleep(1);

    printf("♪ 哈哈哈哈基米来来来搞搞核酸 ♪\n");
    sleep(1);

    printf("♪ 你看你爹操作这波 ♪\n");
    sleep(1);

    printf("♪ OK前十是谁呢 ♪\n");
    sleep(1);

    printf("♪ 圆头耄耋和牢财 ♪\n");
    sleep(1);

    printf("♪ 胖宝宝U好可爱UAUV小白手套 ♪\n");
    sleep(1);

    printf("♪ 韭菜盒子吃两个 ♪\n");
    sleep(1);

    printf("♪ 缺的营养谁给我补啊 ♪\n");
    sleep(1);

    printf("♪ 别吃别吃，阿米诺斯，曼波曼波，我错啦 ♪\n");
    sleep(1);

    printf("\n===================================\n");
    printf("耄耋已被拯救！\n");
    printf("===================================\n\n");
    sleep(1);

    

    // Read flag from file
    FILE *fp = fopen("/flag.txt", "r");
    if (fp == NULL) {
        printf("哈气!\n");
        printf("flag{test}\n");
        return 1;
    }

    char flag[256];
    if (fgets(flag, sizeof(flag), fp) != NULL) {
        // Remove trailing newline if present
        size_t len = strlen(flag);
        if (len > 0 && flag[len-1] == '\n') {
            flag[len-1] = '\0';
        }
        printf("这是耄耋给你的奖励\n");
        printf("%s\n", flag);
    } else {
        printf("耄耋似了!\n");
    }

    fclose(fp);

    return 0;
}