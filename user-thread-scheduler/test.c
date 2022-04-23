#include <stdio.h>
#include "scheduler.h"

void* func1(void* arg)
{
	for (int i = 0; i < 10; i++) {
		printf("func1 %d\n", i);
		yield();
	}
	printf("func1 returned\n");
}

void* func2(void* arg)
{
	for (int i = 0; i < 10; i++) {
		printf("func2 %d\n", i);
		yield();
	}
	printf("func2 returned\n");
}

void* func3(void* arg)
{
	for (int i = 0; i < 10; i++) {
		printf("func3 %d\n", i);
		yield();
	}
	printf("func3 returned\n");
}

void* func4(void* arg)
{
	for (int i = 0; i < 10; i++) {
		printf("func4 %d\n", i);
		yield();
	}
	printf("func4 returned\n");
}

int main(int argc, char const *argv[])
{
	int task_n = 4;
	task_t tasks[task_n];
	tasks[0].id = get_unique_id();
	tasks[0].grp_id = 1;
	tasks[0].func = func1;
	tasks[0].arg = NULL;
	tasks[0].stack_size = TASK_STACKSIZE;

	tasks[1].id = get_unique_id();
	tasks[1].grp_id = 1;
	tasks[1].func = func2;
	tasks[1].arg = NULL;
	tasks[1].stack_size = TASK_STACKSIZE;

	tasks[2].id = get_unique_id();
	tasks[2].grp_id = 1;
	tasks[2].func = func3;
	tasks[2].arg = NULL;
	tasks[2].stack_size = TASK_STACKSIZE;
	
	tasks[3].id = get_unique_id();
	tasks[3].grp_id = 1;
	tasks[3].func = func4;
	tasks[3].arg = NULL;
	tasks[3].stack_size = TASK_STACKSIZE;

	run_tasks(tasks, task_n);
	printf("Done\n");
	return 0;
}
