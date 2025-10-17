#include <pthread.h>
#include <semaphore.h>
#include <stdlib.h>
#include <stdio.h>
#include <ctype.h>
#include <string.h>
#include <time.h>

pthread_mutex_t mutex;
int wordCnt = 0;

typedef struct
{
    long start;
    long stop;
} FunctionArgs;

static void *count_words(void *arg)
{
    FunctionArgs *args = (FunctionArgs *)arg;
    long start = args->start;
    long stop = args->stop;

    FILE *text = fopen("Java.txt", "r");
    if (text == NULL)
    {
        printf("Error: Could not open Java.txt file\n");
        return NULL;
    }

    fseek(text, start, SEEK_SET);
    int in_word = 0;

    while (ftell(text) < stop && (c = fgetc(text)) != EOF)
    {
        if (isalnum(c) && !in_word)
        {
            in_word = 1;
        }
        else if (!isalnum(c) && in_word)
        {
            pthread_mutex_lock(&mutex);
            wordCnt++;
            pthread_mutex_unlock(&mutex);
            in_word = 0;
        }
    }

    fclose(text);
    return NULL;
}

int main(int argc, char *argv[])
{
    clock_t start, end;
    double execution_time;
    int threadNum = atoi(argv[1]);
    // Get actual file size instead of using hardcoded value
    FILE *text = fopen("Java.txt", "r");
    char c;
    long charCnt = 0;

    if (text == NULL)
    {
        printf("Error: Could not open Java.txt file\n");
        return 1;
    }

    // Get file size
    fseek(text, 0, SEEK_END);
    charCnt = ftell(text);
    fseek(text, 0, SEEK_SET);
    fclose(text);

    start = clock();
    pthread_t threads[threadNum];
    FunctionArgs args[threadNum];
    pthread_mutex_init(&mutex, NULL);
    for (int i = 0; i < threadNum; i++)
    {
        args[i].start = (charCnt / threadNum) * i;
        if (i != threadNum - 1)
        {
            args[i].stop = args[i].start + (charCnt / threadNum) - 1;
        }
        else
        {
            args[i].stop = charCnt;
        }
    }
    for (int i = 0; i < threadNum; i++)
    {
        pthread_create(&threads[i], NULL, count_words, &args[i]);
    }
    for (int i = 0; i < threadNum; i++)
    {
        pthread_join(threads[i], NULL);
    }

    printf("Word Count = %d\n", wordCnt);
    pthread_mutex_destroy(&mutex);
    end = clock();
    execution_time = (double)(end - start);
    printf("Execution Time = %f\n", execution_time);
}